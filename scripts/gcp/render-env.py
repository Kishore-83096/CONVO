#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def pick(values: dict[str, str], key: str, default: str = "") -> str:
    return values.get(key, "").strip() or default


def identity_env(values: dict[str, str], messenger_url: str, sync_required: str) -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "JWT_ISSUER": pick(values, "JWT_ISSUER", "myna-identity-service"),
        "JWT_ACCESS_TOKEN_HOURS": pick(values, "JWT_ACCESS_TOKEN_HOURS", "24"),
        "JWT_REFRESH_TOKEN_DAYS": pick(values, "JWT_REFRESH_TOKEN_DAYS", "30"),
        "FRONTEND_ORIGINS": pick(values, "GCP_FRONTEND_ORIGINS"),
        "CLOUDINARY_FOLDER": pick(values, "IDENTITY_CLOUDINARY_FOLDER", "Mynav2/production/profiles"),
        "PROFILE_IMAGE_MAX_BYTES": pick(values, "PROFILE_IMAGE_MAX_BYTES", "5242880"),
        "MAX_REQUEST_BYTES": pick(values, "MAX_REQUEST_BYTES", "6291456"),
        "LOG_LEVEL": pick(values, "LOG_LEVEL", "INFO"),
        "RATELIMIT_STORAGE_URI": "memory://",
        "REGISTER_RATE_LIMIT": pick(values, "REGISTER_RATE_LIMIT", "5 per minute"),
        "LOGIN_RATE_LIMIT": pick(values, "LOGIN_RATE_LIMIT", "10 per minute"),
        "RESET_PASSWORD_RATE_LIMIT": pick(values, "RESET_PASSWORD_RATE_LIMIT", "5 per minute"),
        "DELETE_ACCOUNT_RATE_LIMIT": pick(values, "DELETE_ACCOUNT_RATE_LIMIT", "3 per minute"),
        "CONTACT_SEARCH_RATE_LIMIT": pick(values, "CONTACT_SEARCH_RATE_LIMIT", "20 per minute"),
        "CONTACT_ADD_RATE_LIMIT": pick(values, "CONTACT_ADD_RATE_LIMIT", "20 per minute"),
        "MESSENGER_SERVICE_BASE_URL": messenger_url.rstrip("/"),
        "MESSENGER_POLICY_SYNC_TIMEOUT_SECONDS": pick(values, "MESSENGER_POLICY_SYNC_TIMEOUT_SECONDS", "3"),
        "MESSENGER_POLICY_SYNC_REQUIRED": sync_required,
        "WEB_CONCURRENCY": pick(values, "IDENTITY_WEB_CONCURRENCY", "4"),
        "GUNICORN_THREADS": pick(values, "IDENTITY_GUNICORN_THREADS", "8"),
        "GUNICORN_TIMEOUT": pick(values, "IDENTITY_GUNICORN_TIMEOUT", "60"),
        "PORT": "8080",
    }


def messenger_env(values: dict[str, str], identity_url: str, messenger_url: str, role: str) -> dict[str, str]:
    result = {
        "APP_ENV": "production",
        "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": pick(values, "GCP_DJANGO_ALLOWED_HOSTS", "*"),
        "DJANGO_CSRF_TRUSTED_ORIGINS": pick(values, "GCP_FRONTEND_ORIGINS"),
        "DJANGO_TIME_ZONE": pick(values, "DJANGO_TIME_ZONE", "UTC"),
        "DJANGO_SECURE_SSL_REDIRECT": "false",
        "DJANGO_SESSION_COOKIE_SECURE": "true",
        "DJANGO_CSRF_COOKIE_SECURE": "true",
        "DJANGO_HSTS_SECONDS": pick(values, "DJANGO_HSTS_SECONDS", "0"),
        "FRONTEND_ORIGINS": pick(values, "GCP_FRONTEND_ORIGINS"),
        "IDENTITY_SERVICE_BASE_URL": identity_url.rstrip("/"),
        "MESSENGER_SERVICE_BASE_URL": messenger_url.rstrip("/"),
        "JWT_ALGORITHM": pick(values, "JWT_ALGORITHM", "HS256"),
        "JWT_IDENTITY_CLAIM": pick(values, "JWT_IDENTITY_CLAIM", "sub"),
        "JWT_TOKEN_TYPE_CLAIM": pick(values, "JWT_TOKEN_TYPE_CLAIM", "type"),
        "JWT_ACCESS_TOKEN_TYPE": pick(values, "JWT_ACCESS_TOKEN_TYPE", "access"),
        "JWT_ISSUER": pick(values, "JWT_ISSUER", "myna-identity-service"),
        "JWT_AUDIENCE": pick(values, "JWT_AUDIENCE"),
        "JWT_LEEWAY_SECONDS": pick(values, "JWT_LEEWAY_SECONDS", "5"),
        "CLOUDINARY_FOLDER": pick(values, "MESSENGER_CLOUDINARY_FOLDER", "Mynav2/production/attachments"),
        "ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS": pick(values, "ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS", "900"),
        "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS": pick(values, "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS", "900"),
        "ATTACHMENT_MIN_TTL_SECONDS": pick(values, "ATTACHMENT_MIN_TTL_SECONDS", "60"),
        "ATTACHMENT_MAX_CIPHERTEXT_BYTES": pick(values, "ATTACHMENT_MAX_CIPHERTEXT_BYTES", "52428800"),
        "ATTACHMENT_CLOUDINARY_RESOURCE_TYPE": pick(values, "ATTACHMENT_CLOUDINARY_RESOURCE_TYPE", "raw"),
        "ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE": pick(values, "ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE", "false"),
        "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS": pick(values, "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS", "300"),
        "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS": pick(values, "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS", "900"),
        "ATTACHMENT_CLEANUP_DELETE_CLOUDINARY": pick(values, "ATTACHMENT_CLEANUP_DELETE_CLOUDINARY", "false"),
        "ATTACHMENT_UNATTACHED_GRACE_HOURS": pick(values, "ATTACHMENT_UNATTACHED_GRACE_HOURS", "24"),
        "MESSENGER_HTTP_SERVER_MODE": pick(values, "MESSENGER_HTTP_SERVER_MODE", "wsgi"),
        "WEB_CONCURRENCY": pick(values, "WEB_CONCURRENCY", "6"),
        "GUNICORN_THREADS": pick(values, "GUNICORN_THREADS", "12"),
        "ASGI_THREADS": pick(values, "ASGI_THREADS", "12"),
        "GUNICORN_WORKER_CONNECTIONS": pick(values, "GUNICORN_WORKER_CONNECTIONS", "30"),
        "GUNICORN_BACKLOG": pick(values, "GUNICORN_BACKLOG", "4096"),
        "GUNICORN_TIMEOUT": pick(values, "GUNICORN_TIMEOUT", "60"),
        "GUNICORN_GRACEFUL_TIMEOUT": pick(values, "GUNICORN_GRACEFUL_TIMEOUT", "30"),
        "GUNICORN_KEEP_ALIVE": pick(values, "GUNICORN_KEEP_ALIVE", "5"),
        "GUNICORN_MAX_REQUESTS": pick(values, "GUNICORN_MAX_REQUESTS", "0"),
        "GUNICORN_MAX_REQUESTS_JITTER": pick(values, "GUNICORN_MAX_REQUESTS_JITTER", "0"),
        "GUNICORN_ACCESS_LOG": pick(values, "GUNICORN_ACCESS_LOG", "1"),
        "DB_CONN_MAX_AGE": pick(values, "DB_CONN_MAX_AGE", "0"),
        "DB_CONN_HEALTH_CHECKS": pick(values, "DB_CONN_HEALTH_CHECKS", "true"),
        "REALTIME_TICKET_TTL_SECONDS": pick(values, "REALTIME_TICKET_TTL_SECONDS", "60"),
        "REALTIME_PRESENCE_TTL_SECONDS": pick(values, "REALTIME_PRESENCE_TTL_SECONDS", "45"),
        "REALTIME_HEARTBEAT_SECONDS": pick(values, "REALTIME_HEARTBEAT_SECONDS", "20"),
        "REALTIME_OUTBOX_BATCH_SIZE": pick(values, "REALTIME_OUTBOX_BATCH_SIZE", "100"),
        "REALTIME_OUTBOX_POLL_INTERVAL_SECONDS": pick(values, "REALTIME_OUTBOX_POLL_INTERVAL_SECONDS", "1"),
        "MYNA_PROFILE_DIRECT_SEND": "false",
        "MYNA_BENCHMARK_ASGI_ACCESS_LOG": "0",
        "MESSENGER_PROCESS_ROLE": role,
        "PORT": "8080",
        "LOG_LEVEL": pick(values, "LOG_LEVEL", "INFO"),
    }
    return result


def write_yaml(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}: {json.dumps(value)}" for key, value in sorted(values.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--role", required=True, choices=("identity", "identity-migrate", "messenger", "messenger-migrate", "outbox"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--identity-url", default="https://pending.invalid/api/v1")
    parser.add_argument("--messenger-url", default="https://pending.invalid")
    parser.add_argument("--sync-required", choices=("true", "false"), default="false")
    args = parser.parse_args()

    values = parse_dotenv(args.env_file)
    if args.role in {"identity", "identity-migrate"}:
        rendered = identity_env(values, args.messenger_url, args.sync_required)
    else:
        process_role = "outbox" if args.role == "outbox" else "http"
        rendered = messenger_env(values, args.identity_url, args.messenger_url, process_role)
    write_yaml(args.output, rendered)


if __name__ == "__main__":
    main()
