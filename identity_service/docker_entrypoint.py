import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

LOCAL_DATABASE_HOSTS = {"127.0.0.1", "localhost", "::1"}
BASE_DIR = Path(__file__).resolve().parent


def normalize_database_url(
    database_url: str | None,
) -> str | None:
    if database_url is None:
        return None

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

    if database_url.startswith(
        "postgresql+psycopg2://"
    ):
        return database_url.replace(
            "postgresql+psycopg2://",
            "postgresql+psycopg://",
            1,
        )

    return database_url


def resolve_container_environment_file() -> Path | None:
    configured_path = os.getenv(
        "IDENTITY_ENV_FILE",
        "",
    ).strip()

    if configured_path:
        env_file = Path(configured_path)
        if not env_file.is_absolute():
            env_file = BASE_DIR / env_file
        return env_file

    environment = os.getenv("APP_ENV", "").strip().lower()
    if environment in {"local", "production"}:
        return BASE_DIR / f".env.{environment}"

    return None


def load_container_environment() -> None:
    env_file = resolve_container_environment_file()

    if env_file and env_file.is_file():
        load_dotenv(env_file, override=False)
        print(
            f"Loaded container environment defaults from {env_file.name}.",
            flush=True,
        )


def validate_container_environment() -> None:
    missing = [
        key
        for key in (
            "APP_ENV",
            "DATABASE_URL",
            "SECRET_KEY",
            "JWT_SECRET_KEY",
        )
        if not os.getenv(key, "").strip()
    ]

    if missing:
        raise RuntimeError(
            "Missing required Docker environment variables: "
            + ", ".join(missing)
            + ". Start the container with --env-file .env.local -e APP_ENV=local "
            + "or provide equivalent environment variables."
        )


def configure_database_host() -> None:
    database_url = normalize_database_url(os.getenv("DATABASE_URL"))

    if not database_url:
        return

    os.environ["DATABASE_URL"] = database_url

    try:
        parsed_url = make_url(database_url)
    except ArgumentError as error:
        raise RuntimeError(
            "DATABASE_URL is invalid. In Render, set DATABASE_URL to "
            "the database URL only (for example, postgresql://...), "
            "without a DATABASE_URL= prefix."
        ) from error

    if parsed_url.host not in LOCAL_DATABASE_HOSTS:
        return

    docker_host = os.getenv("IDENTITY_DOCKER_HOST", "host.docker.internal")
    os.environ["DATABASE_URL"] = parsed_url.set(
        host=docker_host,
    ).render_as_string(hide_password=False)


def run_database_migrations() -> None:
    print("Applying database migrations...", flush=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "flask",
            "--app",
            "identity_service:app",
            "db",
            "upgrade",
        ],
        check=True,
    )
    print("Database migrations are up to date.", flush=True)


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("No container command was provided.")

    load_container_environment()
    validate_container_environment()
    configure_database_host()
    run_database_migrations()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
