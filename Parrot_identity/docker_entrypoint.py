import os
import sys

from sqlalchemy.engine import make_url


LOCAL_DATABASE_HOSTS = {"127.0.0.1", "localhost", "::1"}


def configure_database_host() -> None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        return

    parsed_url = make_url(database_url)

    if parsed_url.host not in LOCAL_DATABASE_HOSTS:
        return

    docker_host = os.getenv(
        "PARROT_DOCKER_HOST",
        "host.docker.internal",
    )
    os.environ["DATABASE_URL"] = parsed_url.set(
        host=docker_host,
    ).render_as_string(hide_password=False)


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("No container command was provided.")

    configure_database_host()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
