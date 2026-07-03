import os

from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"sslmode": "require"}}
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    BASIC_AUTH_USERNAME = os.environ.get("BASIC_AUTH_USERNAME", "")
    BASIC_AUTH_PASSWORD = os.environ.get("BASIC_AUTH_PASSWORD", "")
