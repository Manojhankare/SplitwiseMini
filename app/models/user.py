from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    monthly_budget = db.Column(db.Numeric(12, 2), nullable=True)
    theme_mode = db.Column(db.String(16), nullable=True)
    theme_accent = db.Column(db.String(16), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    THEME_MODES = frozenset({"light", "dark"})
    THEME_ACCENTS = frozenset({"indigo", "teal", "rose", "amber", "slate"})

    people = db.relationship("Person", backref="user", cascade="all, delete-orphan")
    groups = db.relationship("Group", backref="user", cascade="all, delete-orphan")
    expenses = db.relationship("Expense", backref="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "monthly_budget": float(self.monthly_budget) if self.monthly_budget is not None else None,
            "theme_mode": self.theme_mode,
            "theme_accent": self.theme_accent,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def set_monthly_budget(cls, user_id, amount):
        user = db.session.get(cls, user_id)
        if not user:
            return None
        user.monthly_budget = amount
        db.session.commit()
        return user

    @classmethod
    def set_theme(cls, user_id, mode, accent):
        if mode not in cls.THEME_MODES or accent not in cls.THEME_ACCENTS:
            return None
        user = db.session.get(cls, user_id)
        if not user:
            return None
        user.theme_mode = mode
        user.theme_accent = accent
        db.session.commit()
        return user

    @classmethod
    def create(cls, username, password, email=None, role="user"):
        normalized_email = email.strip().lower() if email else None
        user = cls(username=username.strip().lower(), email=normalized_email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    @classmethod
    def get_by_username(cls, username):
        return cls.query.filter_by(username=username.strip().lower()).first()

    @classmethod
    def get_by_email(cls, email):
        if not email:
            return None
        return cls.query.filter_by(email=email.strip().lower()).first()

    @classmethod
    def list_all(cls):
        return cls.query.order_by(cls.created_at.desc()).all()

    @classmethod
    def delete_user(cls, user_id):
        user = db.session.get(cls, user_id)
        if user:
            db.session.delete(user)
            db.session.commit()

    @classmethod
    def set_user_password(cls, user_id, password):
        user = db.session.get(cls, user_id)
        if not user or user.role == "admin":
            return None
        user.set_password(password)
        db.session.commit()
        return user

    @classmethod
    def toggle_active(cls, user_id):
        user = db.session.get(cls, user_id)
        if user and user.role != "admin":
            user.is_active = not user.is_active
            db.session.commit()
            return user
        return None
