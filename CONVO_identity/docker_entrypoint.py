import os
import subprocess
import sys

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.config import normalize_database_url


LOCAL_DATABASE_HOSTS = {"127.0.0.1", "localhost", "::1"}


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

    docker_host = os.getenv(
        "PARROT_DOCKER_HOST",
        "host.docker.internal",
    )
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
            "parrot_identity:app",
            "db",
            "upgrade",
        ],
        check=True,
    )
    print("Database migrations are up to date.", flush=True)


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("No container command was provided.")

    configure_database_host()
    run_database_migrations()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
