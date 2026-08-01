from datetime import datetime, timezone

from sqlalchemy import Index

from app.extensions import db


def _equal_shares(amount, participants, all_people):
    shares = {p: 0.0 for p in all_people}
    if not participants:
        return shares
    amount_cents = int(round(float(amount) * 100))
    n = len(participants)
    base_cents = amount_cents // n
    remainder = amount_cents % n
    for i, p in enumerate(participants):
        cents = base_cents + (1 if i < remainder else 0)
        shares[p] = cents / 100.0
    return shares


def _split_type(row):
    if row.is_personal or len(row.participants) == 1:
        return f"{row.payer} only"
    return f"{len(row.participants)}-way split"


class Expense(db.Model):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_user_id_expense_date", "user_id", "expense_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric, nullable=False)
    payer = db.Column(db.Text, nullable=False)
    participants = db.Column(db.JSON, nullable=False)
    expense_date = db.Column(
        db.Date,
        default=lambda: datetime.now(timezone.utc).date(),
        nullable=False,
    )
    is_personal = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "amount": float(self.amount),
            "payer": self.payer,
            "participants": self.participants,
            "date": self.expense_date.isoformat(),
            "is_personal": self.is_personal,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def create(cls, user_id, description, amount, payer, participants, expense_date=None, is_personal=False):
        if is_personal:
            participants = [payer]
        exp = cls(
            user_id=user_id,
            description=description,
            amount=amount,
            payer=payer,
            participants=participants,
            expense_date=expense_date or datetime.now(timezone.utc).date(),
            is_personal=is_personal,
        )
        db.session.add(exp)
        db.session.commit()
        return exp

    @classmethod
    def update(cls, expense_id, user_id, description, amount, payer, participants, expense_date=None, is_personal=False):
        exp = cls.get_for_user(expense_id, user_id)
        if not exp:
            return None
        if is_personal:
            participants = [payer]
        exp.description = description
        exp.amount = amount
        exp.payer = payer
        exp.participants = participants
        exp.is_personal = is_personal
        if expense_date is not None:
            exp.expense_date = expense_date
        db.session.commit()
        return exp

    @classmethod
    def _query_for_user(cls, user_id):
        return cls.query.filter_by(user_id=user_id)

    @classmethod
    def fetch_for_user(cls, user_id, start_date=None, end_date=None):
        q = cls._query_for_user(user_id)
        if start_date is not None:
            q = q.filter(cls.expense_date >= start_date)
        if end_date is not None:
            q = q.filter(cls.expense_date <= end_date)
        return (
            q.order_by(cls.expense_date.desc(), cls.created_at.desc())
            .all()
        )

    @classmethod
    def list_all(cls, user_id, start_date=None, end_date=None):
        return cls.to_dicts_with_outstanding(
            cls.fetch_for_user(user_id, start_date=start_date, end_date=end_date),
            user_id,
        )

    @classmethod
    def get_for_user(cls, expense_id, user_id):
        return cls._query_for_user(user_id).filter_by(id=expense_id).first()

    @classmethod
    def delete(cls, expense_id, user_id):
        exp = cls.get_for_user(expense_id, user_id)
        if exp:
            db.session.delete(exp)
            db.session.commit()

    @classmethod
    def _has_outstanding(cls, expense, ledger=None):
        if expense.is_personal:
            return False
        if ledger is None:
            ledger = cls._build_settlement_ledger(expense.user_id, expense.payer)
        for p in (expense.participants or []):
            if p == expense.payer:
                continue
            if float(ledger.get(p, {}).get(expense.id, 0.0)) > 0.001:
                return True
        return False

    @classmethod
    def _build_settlement_ledger(cls, user_id, payer, expenses=None, settlements=None):
        """FIFO-allocated outstanding per debtor per bill, for bills paid by `payer`.

        Returns {debtor: {expense_id: outstanding_amount}}.

        Linked settlements are already exact per-bill (via settled_by_person_for_expense,
        unchanged). Only the *unlinked* pool per debtor needs allocation, and it is
        allocated against that debtor's bills with this payer oldest-first (FIFO), so a
        general settle-up permanently clears the bills it covered even if new, unrelated
        debt accrues afterward (instead of a single all-time aggregate number that lets
        later debt make an already-settled bill look outstanding again).

        Scoped to the same direction only (debtor -> payer). Does not net against the
        reverse direction (payer -> debtor), which is a separate ledger call when that
        debtor is themselves a payer elsewhere. Known limitation: if two people frequently
        swap payer/debtor roles with each other, each direction is tracked independently.
        """
        from app.models.settlement import Settlement

        if expenses is None:
            expenses = cls.fetch_for_user(user_id)
        if settlements is None:
            settlements = Settlement.fetch_for_user(user_id)

        payer_bills = [e for e in expenses if not e.is_personal and e.payer == payer]
        bill_ids = [e.id for e in payer_bills]
        linked_settled = Settlement.settled_by_expense_ids(user_id, bill_ids)

        unlinked_pool = {}
        for s in settlements:
            if s.expense_id is not None or s.to_person != payer:
                continue
            unlinked_pool[s.from_person] = unlinked_pool.get(s.from_person, 0.0) + float(s.amount)

        by_debtor = {}
        for e in sorted(payer_bills, key=lambda e: (e.expense_date, e.id)):
            shares = _equal_shares(float(e.amount), e.participants or [], e.participants or [])
            for p in (e.participants or []):
                if p == payer:
                    continue
                remaining = round(shares.get(p, 0.0) - linked_settled.get(e.id, {}).get(p, 0.0), 2)
                if remaining > 0.001:
                    by_debtor.setdefault(p, []).append((e.id, remaining))

        ledger = {}
        for debtor, bills in by_debtor.items():
            pool_left = max(0.0, unlinked_pool.get(debtor, 0.0))
            ledger[debtor] = {}
            for expense_id, remaining in bills:
                consumed = min(remaining, pool_left)
                ledger[debtor][expense_id] = round(remaining - consumed, 2)
                pool_left -= consumed
        return ledger

    @classmethod
    def to_dicts_with_outstanding(cls, expenses, user_id, all_expenses=None, all_settlements=None):
        """Serialize expenses; has_outstanding uses a per-payer FIFO settlement ledger.

        `all_expenses`/`all_settlements` let a caller that already has the all-time lists
        (e.g. bootstrap_payload when the active period is already "All time") pass them in
        to avoid a duplicate all-time fetch. Fetched once here (not once per distinct payer).
        """
        from app.models.settlement import Settlement

        shared = [e for e in expenses if not e.is_personal]

        if all_expenses is None:
            all_expenses = cls.fetch_for_user(user_id)
        if all_settlements is None:
            all_settlements = Settlement.fetch_for_user(user_id)

        ledgers = {}
        for e in shared:
            if e.payer not in ledgers:
                ledgers[e.payer] = cls._build_settlement_ledger(
                    user_id, e.payer, expenses=all_expenses, settlements=all_settlements
                )
        result = []
        for e in expenses:
            d = e.to_dict()
            d["has_outstanding"] = cls._has_outstanding(e, ledgers.get(e.payer))
            result.append(d)
        return result

    @classmethod
    def compute_balances(cls, user_id, expenses=None, settlements=None):
        from app.models.settlement import Settlement

        if expenses is None:
            expenses = cls.fetch_for_user(user_id)
        if settlements is None:
            settlements = Settlement.fetch_for_user(user_id)

        net = {}
        for row in expenses:
            if row.is_personal:
                continue
            amount = float(row.amount)
            parts = row.participants or []
            if not parts:
                continue
            shares = _equal_shares(amount, parts, parts)
            net[row.payer] = net.get(row.payer, 0.0) + amount
            for p in parts:
                net[p] = net.get(p, 0.0) - shares.get(p, 0.0)
        net = Settlement.apply_to_balances(user_id, net, settlements=settlements)
        return {k: round(v, 2) for k, v in net.items()}

    @classmethod
    def pairwise_amount_owed(cls, user_id, from_person, to_person, expenses=None, settlements=None):
        """How much from_person currently owes to_person (all-time pairwise), or 0."""
        summary = cls.compute_pairwise_with_self(
            user_id, me=to_person, expenses=expenses, settlements=settlements
        )
        for entry in summary.get("owe_you") or []:
            if entry.get("person") == from_person:
                return float(entry.get("amount") or 0)
        return 0.0

    @classmethod
    def outstanding_for_expense(cls, expense, ledger=None):
        if expense.is_personal:
            return {"payer": expense.payer, "outstanding": {}, "settled": {}}

        amount = float(expense.amount)
        participants = expense.participants or []
        shares = _equal_shares(amount, participants, participants)
        payer = expense.payer
        if ledger is None:
            ledger = cls._build_settlement_ledger(expense.user_id, payer)

        outstanding = {}
        settled_people = {}
        for p in participants:
            if p == payer:
                continue
            share = shares.get(p, 0.0)
            # The FIFO ledger already resolves linked settlements on this bill plus this
            # debtor's oldest-first share of the all-time unlinked settlement pool.
            owed = float(ledger.get(p, {}).get(expense.id, 0.0))
            if owed > 0.001:
                outstanding[p] = owed
            else:
                settled_people[p] = share

        return {
            "expense_id": expense.id,
            "payer": payer,
            "description": expense.description,
            "outstanding": outstanding,
            "settled": settled_people,
        }

    @classmethod
    def compute_pairwise_with_self(cls, user_id, me="self", expenses=None, settlements=None):
        from app.models.settlement import Settlement

        if expenses is None:
            expenses = cls.fetch_for_user(user_id)
        if settlements is None:
            settlements = Settlement.fetch_for_user(user_id)

        pairwise = {}
        for row in expenses:
            if row.is_personal:
                continue
            amount = float(row.amount)
            parts = row.participants or []
            if not parts:
                continue
            shares = _equal_shares(amount, parts, parts)
            payer = row.payer
            if payer == me:
                for p in parts:
                    if p != me:
                        pairwise[p] = pairwise.get(p, 0.0) + shares.get(p, 0.0)
            elif me in parts:
                pairwise[payer] = pairwise.get(payer, 0.0) - shares.get(me, 0.0)

        for row in settlements:
            amount = float(row.amount)
            if row.to_person == me:
                pairwise[row.from_person] = pairwise.get(row.from_person, 0.0) - amount
            elif row.from_person == me:
                pairwise[row.to_person] = pairwise.get(row.to_person, 0.0) + amount

        owe_you = []
        you_owe = []
        for person in sorted(pairwise):
            amt = round(pairwise[person], 2)
            if amt > 0.001:
                owe_you.append({"person": person, "amount": amt})
            elif amt < -0.001:
                you_owe.append({"person": person, "amount": round(-amt, 2)})

        return {"owe_you": owe_you, "you_owe": you_owe}

    @classmethod
    def compute_report(cls, user_id, filter_type="all", expenses=None, settlements=None):
        if expenses is None:
            expenses = cls.fetch_for_user(user_id)

        people_set = set()
        for row in expenses:
            people_set.add(row.payer)
            people_set.update(row.participants)
        people = sorted(people_set)

        report_rows = []
        totals = {p: 0.0 for p in people}
        grand_total = 0.0

        for row in expenses:
            if filter_type == "shared" and row.is_personal:
                continue
            if filter_type == "personal" and not row.is_personal:
                continue

            amount = float(row.amount)
            if row.is_personal:
                shares = {p: 0.0 for p in people}
                shares[row.payer] = amount
            else:
                shares = _equal_shares(amount, row.participants, people)

            for p in people:
                totals[p] += shares[p]
            grand_total += amount

            report_rows.append({
                "id": row.id,
                "date": row.expense_date.isoformat(),
                "description": row.description,
                "amount": amount,
                "payer": row.payer,
                "is_personal": row.is_personal,
                "shares": {p: round(shares[p], 2) for p in people},
                "split_type": _split_type(row),
            })

        return {
            "people": people,
            "rows": report_rows,
            "totals": {p: round(totals[p], 2) for p in people},
            "grand_total": round(grand_total, 2),
            "self_summary": cls.compute_pairwise_with_self(
                user_id, expenses=expenses, settlements=settlements
            ),
        }

    @classmethod
    def compute_monthly_budget_summary(cls, user_id, me="self"):
        """Consumption budget for the current UTC calendar month.

        Separate from bootstrap period filters. Settlements are ignored.
        """
        from calendar import monthrange

        from app.models.user import User

        now = datetime.now(timezone.utc).date()
        start = now.replace(day=1)
        end = now.replace(day=monthrange(now.year, now.month)[1])
        month_expenses = cls.fetch_for_user(user_id, start_date=start, end_date=end)

        budget_personal = 0.0
        budget_my_shared = 0.0
        budget_shared_total = 0.0

        for row in month_expenses:
            amount = float(row.amount)
            if row.is_personal:
                if row.payer == me:
                    budget_personal += amount
                continue

            budget_shared_total += amount
            parts = row.participants or []
            if me not in parts:
                continue
            shares = _equal_shares(amount, parts, parts)
            budget_my_shared += shares.get(me, 0.0)

        budget_personal = round(budget_personal, 2)
        budget_my_shared = round(budget_my_shared, 2)
        budget_spent = round(budget_personal + budget_my_shared, 2)
        budget_shared_total = round(budget_shared_total, 2)

        user = db.session.get(User, user_id)
        monthly_budget = (
            float(user.monthly_budget) if user and user.monthly_budget is not None else None
        )

        return {
            "monthly_budget": monthly_budget,
            "budget_personal": budget_personal,
            "budget_my_shared": budget_my_shared,
            "budget_spent": budget_spent,
            "budget_shared_total": budget_shared_total,
        }

    @classmethod
    def bootstrap_payload(cls, user_id, filter_type="all", start_date=None, end_date=None):
        from app.models.group import Group
        from app.models.person import Person
        from app.models.settlement import Settlement

        expenses = cls.fetch_for_user(user_id, start_date=start_date, end_date=end_date)
        # History list still by settlement_date; balance math uses linked-follow-expense rule.
        settlements_list = Settlement.fetch_for_user(
            user_id, start_date=start_date, end_date=end_date
        )
        period_ids = [e.id for e in expenses]
        balance_settlements = Settlement.fetch_for_balance_period(
            user_id, period_ids, start_date=start_date, end_date=end_date
        )
        # When the active period is already "All time", expenses/settlements_list above
        # already are the all-time lists — reuse them instead of re-fetching for the ledger.
        is_all_time = start_date is None and end_date is None
        payload = {
            "people": Person.list_all(user_id),
            "groups": Group.list_all(user_id),
            "expenses": cls.to_dicts_with_outstanding(
                expenses,
                user_id,
                all_expenses=expenses if is_all_time else None,
                all_settlements=settlements_list if is_all_time else None,
            ),
            "settlements": [r.to_dict() for r in settlements_list],
            "balances": cls.compute_balances(
                user_id, expenses=expenses, settlements=balance_settlements
            ),
            "report": cls.compute_report(
                user_id,
                filter_type=filter_type,
                expenses=expenses,
                settlements=balance_settlements,
            ),
        }
        payload.update(cls.compute_monthly_budget_summary(user_id))
        return payload
