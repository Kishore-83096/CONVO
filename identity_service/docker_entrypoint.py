import os
import sys

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def normalize_database_url(database_url: str | None) -> str | None:
    if database_url is None:
        return None

    value = database_url.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()

    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql+psycopg2://"):
        return value.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    return value


def validate_container_environment() -> None:
    missing = [
        key
        for key in ("APP_ENV", "DATABASE_URL", "SECRET_KEY", "JWT_SECRET_KEY")
        if not os.getenv(key, "").strip()
    ]
    if missing:
        raise RuntimeError(
            "Missing required Identity environment variables: " + ", ".join(missing)
        )

    database_url = normalize_database_url(os.getenv("DATABASE_URL"))
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")
    try:
        make_url(database_url)
    except ArgumentError as error:
        raise RuntimeError("DATABASE_URL is invalid.") from error
    os.environ["DATABASE_URL"] = database_url


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("No container command was provided.")

    # Compose/Cloud Run inject the complete runtime environment. Database
    # migrations are deployment work: compose uses identity-migrate and GCP uses
    # a Cloud Run Job. Runtime service instances never migrate on startup.
    validate_container_environment()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
