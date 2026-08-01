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
    def _has_outstanding(cls, expense, settled=None):
        if expense.is_personal:
            return False
        if settled is None:
            from app.models.settlement import Settlement
            settled = Settlement.settled_by_person_for_expense(expense.user_id, expense.id)
        amount = float(expense.amount)
        participants = expense.participants
        shares = _equal_shares(amount, participants, participants)
        for p in participants:
            if p == expense.payer:
                continue
            owed = round(shares.get(p, 0.0) - settled.get(p, 0.0), 2)
            if owed > 0.001:
                return True
        return False

    @classmethod
    def to_dicts_with_outstanding(cls, expenses, user_id):
        """Serialize expenses; has_outstanding uses all-time settlements for that bill."""
        from app.models.settlement import Settlement

        shared_ids = [e.id for e in expenses if not e.is_personal]
        settled_map = Settlement.settled_by_expense_ids(user_id, shared_ids)
        result = []
        for e in expenses:
            d = e.to_dict()
            d["has_outstanding"] = cls._has_outstanding(e, settled_map.get(e.id, {}))
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
            share = amount / len(row.participants)
            net[row.payer] = net.get(row.payer, 0.0) + amount
            for p in row.participants:
                net[p] = net.get(p, 0.0) - share
        net = Settlement.apply_to_balances(user_id, net, settlements=settlements)
        return {k: round(v, 2) for k, v in net.items()}

    @classmethod
    def outstanding_for_expense(cls, expense):
        from app.models.settlement import Settlement

        if expense.is_personal:
            return {"payer": expense.payer, "outstanding": {}, "settled": {}}

        amount = float(expense.amount)
        participants = expense.participants
        shares = _equal_shares(amount, participants, participants)
        settled = Settlement.settled_by_person_for_expense(expense.user_id, expense.id)

        outstanding = {}
        settled_people = {}
        for p in participants:
            if p == expense.payer:
                continue
            share = shares.get(p, 0.0)
            paid = round(settled.get(p, 0.0), 2)
            owed = round(share - paid, 2)
            if owed > 0.001:
                outstanding[p] = owed
            elif paid > 0.001 or share <= 0.001:
                settled_people[p] = round(share if share > 0 else paid, 2)

        return {
            "expense_id": expense.id,
            "payer": expense.payer,
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
            share = amount / len(row.participants)
            payer = row.payer
            if payer == me:
                for p in row.participants:
                    if p != me:
                        pairwise[p] = pairwise.get(p, 0.0) + share
            elif me in row.participants:
                pairwise[payer] = pairwise.get(payer, 0.0) - share

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
    def bootstrap_payload(cls, user_id, filter_type="all", start_date=None, end_date=None):
        from app.models.group import Group
        from app.models.person import Person
        from app.models.settlement import Settlement

        expenses = cls.fetch_for_user(user_id, start_date=start_date, end_date=end_date)
        settlements = Settlement.fetch_for_user(user_id, start_date=start_date, end_date=end_date)
        return {
            "people": Person.list_all(user_id),
            "groups": Group.list_all(user_id),
            "expenses": cls.to_dicts_with_outstanding(expenses, user_id),
            "settlements": [r.to_dict() for r in settlements],
            "balances": cls.compute_balances(
                user_id, expenses=expenses, settlements=settlements
            ),
            "report": cls.compute_report(
                user_id,
                filter_type=filter_type,
                expenses=expenses,
                settlements=settlements,
            ),
        }
