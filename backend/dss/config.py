"""Environment configuration shared by the Flask app and psycopg2 layer."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(PROJECT_DIR / ".env", override=True)

TRUTHY = {"1", "true", "yes", "on"}


def _bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in TRUTHY


def _list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config() -> dict:
    """Read the same variable names as the former Django ``EnvConfig``."""
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY", ""),
        "DEBUG": _bool(
            os.environ.get("FLASK_DEBUG", os.environ.get("DJANGO_DEBUG", "true"))
        ),
        "POSTGRES_DB": os.environ.get("POSTGRES_DB", "tam_soat_dot_quy"),
        "POSTGRES_USER": os.environ.get("POSTGRES_USER", "postgres"),
        "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", "password"),
        "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CORS_ALLOW_ALL_ORIGINS": _bool(
            os.environ.get("CORS_ALLOW_ALL_ORIGINS", "true")
        ),
        "CORS_ALLOWED_ORIGINS": _list(
            os.environ.get(
                "CORS_ALLOWED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,"
                "http://localhost:8080,http://127.0.0.1:8080",
            )
        ),
        # Optional host allow-list, mirroring DJANGO_ALLOWED_HOSTS.  Empty means
        # no host filtering (Flask/Werkzeug default).
        "TRUSTED_HOSTS": _list(os.environ.get("DJANGO_ALLOWED_HOSTS", "")) or None,
    }


def postgres_settings(config: dict | None = None) -> dict:
    cfg = config or load_config()
    return {
        "dbname": cfg["POSTGRES_DB"],
        "user": cfg["POSTGRES_USER"],
        "password": cfg["POSTGRES_PASSWORD"],
        "host": cfg["POSTGRES_HOST"],
        "port": cfg["POSTGRES_PORT"],
    }
