import pytest

from app.config import normalize_database_url


@pytest.mark.parametrize(
    ("database_url", "expected_scheme"),
    [
        ("postgres://user:pass@host/database", "postgresql+psycopg"),
        ("postgresql://user:pass@host/database", "postgresql+psycopg"),
        (
            "postgresql+psycopg://user:pass@host/database",
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
