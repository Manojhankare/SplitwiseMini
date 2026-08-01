from datetime import datetime, timezone

from sqlalchemy import Index, func
from sqlalchemy.orm import joinedload

from app.extensions import db


class Settlement(db.Model):
    __tablename__ = "settlements"
    __table_args__ = (
        Index("ix_settlements_user_id_settlement_date", "user_id", "settlement_date"),
        Index("ix_settlements_expense_id", "expense_id"),
    )

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
    def fetch_for_user(cls, user_id, start_date=None, end_date=None):
        q = cls._query_for_user(user_id)
        if start_date is not None:
            q = q.filter(cls.settlement_date >= start_date)
        if end_date is not None:
            q = q.filter(cls.settlement_date <= end_date)
        return (
            q.options(joinedload(cls.expense))
            .order_by(cls.settlement_date.desc(), cls.created_at.desc())
            .all()
        )

    @classmethod
    def list_all(cls, user_id, start_date=None, end_date=None):
        return [r.to_dict() for r in cls.fetch_for_user(user_id, start_date=start_date, end_date=end_date)]

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
    def settled_by_expense_ids(cls, user_id, expense_ids):
        """All-time settled amounts keyed by expense_id -> {person: total}. Not period-scoped."""
        if not expense_ids:
            return {}
        rows = (
            cls._query_for_user(user_id)
            .filter(cls.expense_id.in_(expense_ids))
            .with_entities(cls.expense_id, cls.from_person, func.sum(cls.amount))
            .group_by(cls.expense_id, cls.from_person)
            .all()
        )
        out = {}
        for expense_id, person, total in rows:
            out.setdefault(expense_id, {})[person] = float(total)
        return out

    @classmethod
    def apply_to_balances(cls, user_id, net, settlements=None):
        if settlements is None:
            settlements = cls.fetch_for_user(user_id)
        for row in settlements:
            amount = float(row.amount)
            net[row.from_person] = net.get(row.from_person, 0.0) + amount
            net[row.to_person] = net.get(row.to_person, 0.0) - amount
        return net
