import os

from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

load_dotenv()


def get_database_url():
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def should_create_db_on_startup():
    """Schema/seed only in local development (or when explicitly enabled)."""
    if os.environ.get("ENABLE_DB_CREATE", "").strip() == "1":
        return True
    return os.environ.get("FLASK_ENV", "").strip().lower() == "development"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # NullPool: safe for Vercel serverless (no held connections across freezes)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": NullPool,
        "connect_args": {"sslmode": "require"},
    }
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
