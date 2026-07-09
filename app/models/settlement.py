from datetime import datetime, timezone

from sqlalchemy import func

from app.extensions import db


class Settlement(db.Model):
    __tablename__ = "settlements"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    from_person = db.Column(db.Text, nullable=False)
    to_person = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric, nullable=False)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=True)
    settlement_date = db.Column(
        db.Date,
        default=lambda: datetime.now(timezone.utc).date(),
        nullable=False,
    )
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    expense = db.relationship("Expense", backref="settlements")

    def to_dict(self):
        return {
            "id": self.id,
            "from_person": self.from_person,
            "to_person": self.to_person,
            "amount": float(self.amount),
            "expense_id": self.expense_id,
            "expense_description": self.expense.description if self.expense else None,
            "date": self.settlement_date.isoformat(),
            "note": self.note,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def _query_for_user(cls, user_id):
        return cls.query.filter_by(user_id=user_id)

    @classmethod
    def list_all(cls, user_id):
        rows = (
            cls._query_for_user(user_id)
            .order_by(cls.settlement_date.desc(), cls.created_at.desc())
            .all()
        )
        return [r.to_dict() for r in rows]

    @classmethod
    def get_for_user(cls, settlement_id, user_id):
        return cls._query_for_user(user_id).filter_by(id=settlement_id).first()

    @classmethod
    def create(cls, user_id, from_person, to_person, amount, expense_id=None, settlement_date=None, note=None):
        settlement = cls(
            user_id=user_id,
            from_person=from_person,
            to_person=to_person,
            amount=amount,
            expense_id=expense_id,
            settlement_date=settlement_date or datetime.now(timezone.utc).date(),
            note=note,
        )
        db.session.add(settlement)
        db.session.commit()
        return settlement

    @classmethod
    def delete(cls, settlement_id, user_id):
        row = cls.get_for_user(settlement_id, user_id)
        if row:
            db.session.delete(row)
            db.session.commit()

    @classmethod
    def settled_by_person_for_expense(cls, user_id, expense_id):
        rows = (
            cls._query_for_user(user_id)
            .filter_by(expense_id=expense_id)
            .with_entities(cls.from_person, func.sum(cls.amount))
            .group_by(cls.from_person)
            .all()
        )
        return {person: float(total) for person, total in rows}

    @classmethod
    def apply_to_balances(cls, user_id, net):
        for row in cls._query_for_user(user_id).all():
            amount = float(row.amount)
            net[row.from_person] = net.get(row.from_person, 0.0) + amount
            net[row.to_person] = net.get(row.to_person, 0.0) - amount
        return net
