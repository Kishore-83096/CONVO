import os

import pytest
from sqlalchemy.engine import make_url

from app import create_app

from app.config import normalize_database_url
from docker_entrypoint import (
    normalize_database_url as normalize_entrypoint_database_url,
    validate_container_environment,
)


@pytest.mark.parametrize(
    ("database_url", "expected_scheme"),
    [
        ("postgres://user:pass@host/database", "postgresql+psycopg"),
        ("postgresql://user:pass@host/database", "postgresql+psycopg"),
        (
            "postgresql+psycopg://user:pass@host/database",
            "postgresql+psycopg",
        ),
        (
            "postgresql+psycopg2://user:pass@host/database",
            "postgresql+psycopg",
        ),
        (
            '  "postgresql://user:pass@host/database"  ',
            "postgresql+psycopg",
        ),
        ("mysql+pymysql://user:pass@host/database", "mysql+pymysql"),
    ],
)
def test_normalize_database_url(database_url, expected_scheme):
    normalized_url = normalize_database_url(database_url)

    assert normalized_url.split("://", 1)[0] == expected_scheme


def test_normalize_database_url_preserves_missing_value():
    assert normalize_database_url(None) is None


def test_normalize_database_url_strips_blank_value():
    assert normalize_database_url("   ") == ""


def test_entrypoint_normalizes_quoted_postgres_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL",
        '  "postgresql://user:pass@db.example.com/database"  ',
    )
    monkeypatch.setenv("SECRET_KEY", "secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-secret")

    validate_container_environment()

    parsed_url = make_url(os.environ["DATABASE_URL"])
    assert parsed_url.drivername == "postgresql+psycopg"
    assert parsed_url.host == "db.example.com"


def test_entrypoint_normalizer_matches_expected_postgres_driver():
    normalized = normalize_entrypoint_database_url(
        "postgresql+psycopg2://user:pass@host/database"
    )

    assert normalized is not None
    assert make_url(normalized).drivername == "postgresql+psycopg"


def test_entrypoint_explains_invalid_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL",
        "DATABASE_URL=postgresql://user:pass@host/database",
    )
    monkeypatch.setenv("SECRET_KEY", "secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-secret")

    with pytest.raises(RuntimeError, match="DATABASE_URL is invalid"):
        validate_container_environment()


def test_validate_container_environment_accepts_required_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:pass@mysql/db")
    monkeypatch.setenv("SECRET_KEY", "secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-secret")

    validate_container_environment()

    assert os.environ["DATABASE_URL"] == "mysql+pymysql://user:pass@mysql/db"


def test_validate_container_environment_explains_missing_values(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(
        RuntimeError,
        match="Missing required Identity environment variables",
    ):
        validate_container_environment()



def test_identity_rejects_redis_rate_limit_storage():
    with pytest.raises(
        RuntimeError,
        match="RATELIMIT_STORAGE_URI must be memory://",
    ):
        create_app(
            {
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SECRET_KEY": "secret",
                "JWT_SECRET_KEY": "jwt-secret",
                "FRONTEND_ORIGINS": [
                    "http://localhost:5173"
                ],
                "RATELIMIT_STORAGE_URI": (
                    "redis://redis:6379/2"
                ),
                "TESTING": True,
            }
        )
