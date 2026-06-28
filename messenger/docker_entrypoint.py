import os
import subprocess
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


LOCAL_DATABASE_HOSTS = {"127.0.0.1", "localhost", "::1"}


def configure_database_host() -> None:
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        return

    parsed_url = urlsplit(database_url)

    if parsed_url.hostname not in LOCAL_DATABASE_HOSTS:
        return

    docker_host = os.getenv("MESSENGER_DOCKER_HOST", "host.docker.internal")

    netloc = docker_host
    if parsed_url.username:
        netloc = parsed_url.username
        if parsed_url.password:
            netloc = f"{netloc}:{parsed_url.password}"
        netloc = f"{netloc}@{docker_host}"
    if parsed_url.port:
        netloc = f"{netloc}:{parsed_url.port}"

    query = urlencode(parse_qsl(parsed_url.query, keep_blank_values=True))
    os.environ["DATABASE_URL"] = urlunsplit(
        (
            parsed_url.scheme,
            netloc,
            parsed_url.path,
            query,
            parsed_url.fragment,
        )
    )


def run_database_migrations() -> None:
    print("Applying database migrations...", flush=True)
    subprocess.run(
        [
            sys.executable,
            "manage.py",
            "migrate",
            "--noinput",
        ],
        check=True,
    )
    print("Database migrations are up to date.", flush=True)


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("No container command was provided.")

    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "messenger_config.settings",
    )
    configure_database_host()
    run_database_migrations()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
