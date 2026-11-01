import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

raw_db_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'lms_judge.db'}")
# Fix compatibility for Render PostgreSQL URI (postgres:// -> postgresql://)
if raw_db_url and raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }
    # Cấu hình Auto-Judge Thread Pool
    JUDGE_MAX_WORKERS = int(os.environ.get("JUDGE_MAX_WORKERS", 2))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
