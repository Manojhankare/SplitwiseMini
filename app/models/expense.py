from datetime import datetime, timezone

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

    id = db.Column(db.Integer, primary_key=True)
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
    def create(cls, description, amount, payer, participants, expense_date=None, is_personal=False):
        if is_personal:
            participants = [payer]
        exp = cls(
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
    def list_all(cls):
        rows = cls.query.order_by(cls.expense_date.desc(), cls.created_at.desc()).all()
        return [r.to_dict() for r in rows]

    @classmethod
    def delete(cls, expense_id):
        exp = db.session.get(cls, expense_id)
        if exp:
            db.session.delete(exp)
            db.session.commit()

    @classmethod
    def compute_balances(cls):
        net = {}
        for row in cls.query.all():
            if row.is_personal:
                continue
            amount = float(row.amount)
            share = amount / len(row.participants)
            net[row.payer] = net.get(row.payer, 0.0) + amount
            for p in row.participants:
                net[p] = net.get(p, 0.0) - share
        return {k: round(v, 2) for k, v in net.items()}

    @classmethod
    def compute_report(cls, filter_type="all"):
        rows = cls.query.order_by(cls.expense_date.desc(), cls.created_at.desc()).all()
        people_set = set()
        for row in rows:
            people_set.add(row.payer)
            people_set.update(row.participants)
        people = sorted(people_set)

        report_rows = []
        totals = {p: 0.0 for p in people}
        grand_total = 0.0

        for row in rows:
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
        }
