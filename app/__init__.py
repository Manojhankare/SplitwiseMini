from flask import Flask
from flask_login import current_user

from app.config import Config, should_create_db_on_startup
from app.controllers import admin_bp, auth_bp, expense_bp, page_bp
from app.extensions import db, login_manager
from app.models.expense import Expense  # noqa: F401
from app.models.group import Group  # noqa: F401
from app.models.person import Person  # noqa: F401
from app.models.settlement import Settlement  # noqa: F401
from app.models.user import User


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def seed_admin(app):
    with app.app_context():
        if User.query.filter_by(role="admin").first():
            return
        username = app.config.get("ADMIN_USERNAME", "").strip().lower()
        password = app.config.get("ADMIN_PASSWORD", "")
        if username and password:
            User.create(username=username, password=password, role="admin")


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    if should_create_db_on_startup():
        with app.app_context():
            db.create_all()
            seed_admin(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(page_bp)
    app.register_blueprint(expense_bp)

    @app.context_processor
    def inject_user():
        if current_user.is_authenticated:
            return {
                "current_username": current_user.username,
                "is_admin": current_user.role == "admin",
            }
        return {}

    return app
