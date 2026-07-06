import os
import sys


def env_value(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def access_logfile() -> str:
    explicit = os.getenv("GUNICORN_ACCESS_LOG_FILE", "").strip()
    if explicit:
        return explicit
    if env_value("GUNICORN_ACCESS_LOG", "1") == "1":
        return "-"
    return "/dev/null"


def main() -> None:
    mode = env_value("MESSENGER_HTTP_SERVER_MODE", "wsgi").lower()
    if mode not in {"asgi", "wsgi"}:
        print(
            "MESSENGER_HTTP_SERVER_MODE must be one of: asgi, wsgi",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)

    args = [
        "gunicorn",
        "messenger_config.asgi:application" if mode == "asgi" else "messenger_config.wsgi:application",
        "--bind",
        f"0.0.0.0:{env_value('PORT', '8000')}",
        "--workers",
        env_value("WEB_CONCURRENCY", "4"),
        "--backlog",
        env_value("GUNICORN_BACKLOG", "4096"),
        "--timeout",
        env_value("GUNICORN_TIMEOUT", "60"),
        "--graceful-timeout",
        env_value("GUNICORN_GRACEFUL_TIMEOUT", "30"),
        "--keep-alive",
        env_value("GUNICORN_KEEP_ALIVE", "5"),
        "--max-requests",
        env_value("GUNICORN_MAX_REQUESTS", "0"),
        "--max-requests-jitter",
        env_value("GUNICORN_MAX_REQUESTS_JITTER", "0"),
        "--access-logfile",
        access_logfile(),
        "--error-logfile",
        "-",
    ]

    if mode == "asgi":
        args.extend(["-k", "uvicorn.workers.UvicornWorker"])
    else:
        args.extend(["--worker-class", "gthread", "--threads", env_value("GUNICORN_THREADS", "8")])

    access_log_format = os.getenv("GUNICORN_ACCESS_LOG_FORMAT", "").strip()
    if access_log_format:
        args.extend(["--access-logformat", access_log_format])

    print(
        "Starting Messenger HTTP server: "
        f"mode={mode} workers={env_value('WEB_CONCURRENCY', '4')} "
        f"asgi_threads={os.getenv('ASGI_THREADS', '')} "
        f"gthread_threads={os.getenv('GUNICORN_THREADS', '')} "
        f"db_conn_max_age={os.getenv('DB_CONN_MAX_AGE', 'role-default')} "
        f"db_conn_health_checks={env_value('DB_CONN_HEALTH_CHECKS', 'true')}",
        flush=True,
    )
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()
