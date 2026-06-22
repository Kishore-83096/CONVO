import os

import pytest
from sqlalchemy.engine import make_url

from app.config import normalize_database_url
from docker_entrypoint import configure_database_host


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
