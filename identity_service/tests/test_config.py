import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.config import normalize_database_url
from docker_entrypoint import (
    configure_database_host,
    resolve_container_environment_file,
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


def test_entrypoint_normalizes_quoted_render_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        '  "postgresql://user:pass@db.example.com/database"  ',
    )

    configure_database_host()

    parsed_url = make_url(os.environ["DATABASE_URL"])
    assert parsed_url.drivername == "postgresql+psycopg"
    assert parsed_url.host == "db.example.com"


def test_entrypoint_explains_invalid_render_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "DATABASE_URL=postgresql://user:pass@host/database",
    )

    with pytest.raises(RuntimeError, match="In Render"):
        configure_database_host()


def test_resolve_container_environment_file_uses_app_env_default(monkeypatch):
    monkeypatch.delenv("IDENTITY_ENV_FILE", raising=False)
    monkeypatch.setenv("APP_ENV", "local")

    env_file = resolve_container_environment_file()

    assert env_file is not None
    assert env_file.name == ".env.local"


def test_resolve_container_environment_file_honors_explicit_path(monkeypatch):
    monkeypatch.setenv("IDENTITY_ENV_FILE", "custom.env")

    env_file = resolve_container_environment_file()

    assert env_file is not None
    assert isinstance(env_file, Path)
    assert env_file.name == "custom.env"


def test_validate_container_environment_accepts_required_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:pass@host/db")
    monkeypatch.setenv("SECRET_KEY", "secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-secret")

    validate_container_environment()


def test_validate_container_environment_explains_missing_values(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Missing required Docker environment variables"):
        validate_container_environment()
