import os
from datetime import timedelta


class Config:
    APP_ENV = os.getenv("APP_ENV", "local")

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "15"))
    )

    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "30"))
    )

    FRONTEND_ORIGIN = os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:5173",
    )

    RATELIMIT_STORAGE_URI = os.getenv(
        "RATELIMIT_STORAGE_URI",
        "memory://",
    )

    CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
    CLOUDINARY_FOLDER = os.getenv(
        "CLOUDINARY_FOLDER",
        "parrot/local/profiles",
    )

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
