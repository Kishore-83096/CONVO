import os
from datetime import timedelta


def normalize_database_url(database_url: str | None) -> str | None:
    if not database_url:
        return database_url

    database_url = database_url.strip()

    if (
        len(database_url) >= 2
        and database_url[0] == database_url[-1]
        and database_url[0] in {'"', "'"}
    ):
        database_url = database_url[1:-1].strip()

    if database_url.startswith("postgres://"):
        return database_url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )

    if database_url.startswith("postgresql://"):
        return database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace(
            "postgresql+psycopg2://",
            "postgresql+psycopg://",
            1,
        )

    return database_url


def parse_comma_separated_values(
    value: str | None,
) -> list[str]:
    if not value:
        return []

    return [
        item.strip().rstrip("/")
        for item in value.split(",")
        if item.strip()
    ]


class Config:
    APP_ENV = os.getenv("APP_ENV", "local")

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.getenv("DATABASE_URL")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_HOURS", "24"))
    )

    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "30"))
    )

    FRONTEND_ORIGINS = parse_comma_separated_values(
        os.getenv(
            "FRONTEND_ORIGIN",
            "http://localhost:5173",
        )
    )

    RATELIMIT_STORAGE_URI = os.getenv(
        "RATELIMIT_STORAGE_URI",
        "memory://",
    )

    CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
    CLOUDINARY_FOLDER = os.getenv(
        "CLOUDINARY_FOLDER",
        "parrotv2/local/profiles",
    )

    PROFILE_IMAGE_MAX_BYTES = int(
        os.getenv(
            "PROFILE_IMAGE_MAX_BYTES",
            str(5 * 1024 * 1024),
        )
    )

    MAX_CONTENT_LENGTH = int(
        os.getenv(
            "MAX_REQUEST_BYTES",
            str(6 * 1024 * 1024),
        )
    )

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")