from flask import Flask

from app.config import Config
from app.controllers import expense_bp, page_bp
from app.extensions import db
from app.models.expense import Expense  # noqa: F401 — register models with metadata
from app.models.person import Person  # noqa: F401


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(page_bp)
    app.register_blueprint(expense_bp)

    return app
