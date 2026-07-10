#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

if [[ -f .env ]]; then
  echo "Refusing to overwrite existing $repo_root/.env" >&2
  echo "For an existing root .env, run: bash ./scripts/update-env-to-postgres.sh" >&2
  exit 2
fi
[[ -f .env.example ]] || { echo ".env.example is missing" >&2; exit 2; }

python3 - "$repo_root" <<'PY'
from __future__ import annotations

import secrets
import sys
from pathlib import Path
from urllib.parse import quote

root = Path(sys.argv[1])
example = root / ".env.example"
out = root / ".env"


def parse_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeError:
        text = path.read_text(encoding="utf-16")
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


identity_sources = [
    root / "identity_service/.env.local",
    root / "identity_service/.env.docker.local",
    root / "identity_service/.env.production",
]
messenger_sources = [
    root / "messenger/.env.docker.local",
    root / "messenger/.env.local",
    root / "messenger/.env.production",
]

identity: dict[str, str] = {}
messenger: dict[str, str] = {}
for path in reversed(identity_sources):
    identity.update(parse_env(path))
for path in reversed(messenger_sources):
    messenger.update(parse_env(path))

base = parse_env(example)
result = dict(base)

identity_keys = {
    "SECRET_KEY", "JWT_SECRET_KEY", "JWT_ISSUER", "JWT_ACCESS_TOKEN_HOURS",
    "JWT_REFRESH_TOKEN_DAYS", "FRONTEND_ORIGINS", "CLOUDINARY_URL",
    "PROFILE_IMAGE_MAX_BYTES", "MAX_REQUEST_BYTES", "LOG_LEVEL",
    "REGISTER_RATE_LIMIT", "LOGIN_RATE_LIMIT", "RESET_PASSWORD_RATE_LIMIT",
    "DELETE_ACCOUNT_RATE_LIMIT", "CONTACT_SEARCH_RATE_LIMIT", "CONTACT_ADD_RATE_LIMIT",
    "MESSENGER_INTERNAL_SECRET", "MESSENGER_POLICY_SYNC_TIMEOUT_SECONDS",
    "MESSENGER_POLICY_SYNC_REQUIRED",
}
messenger_keys = {
    "DJANGO_SECRET_KEY", "DJANGO_DEBUG", "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS", "DJANGO_TIME_ZONE", "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SESSION_COOKIE_SECURE", "DJANGO_CSRF_COOKIE_SECURE", "DJANGO_HSTS_SECONDS",
    "JWT_ALGORITHM", "JWT_IDENTITY_CLAIM", "JWT_TOKEN_TYPE_CLAIM",
    "JWT_ACCESS_TOKEN_TYPE", "JWT_AUDIENCE", "JWT_LEEWAY_SECONDS",
    "ATTACHMENT_UPLOAD_SIGNATURE_TTL_SECONDS", "ATTACHMENT_UPLOAD_MAX_TTL_SECONDS",
    "ATTACHMENT_MIN_TTL_SECONDS", "ATTACHMENT_MAX_CIPHERTEXT_BYTES",
    "ATTACHMENT_CLOUDINARY_RESOURCE_TYPE", "ATTACHMENT_VERIFY_CLOUDINARY_ON_COMPLETE",
    "ATTACHMENT_DOWNLOAD_URL_TTL_SECONDS", "ATTACHMENT_DOWNLOAD_URL_MAX_TTL_SECONDS",
    "ATTACHMENT_CLEANUP_DELETE_CLOUDINARY", "ATTACHMENT_UNATTACHED_GRACE_HOURS",
    "MESSENGER_HTTP_SERVER_MODE", "WEB_CONCURRENCY", "GUNICORN_THREADS", "ASGI_THREADS",
    "GUNICORN_WORKER_CONNECTIONS", "GUNICORN_BACKLOG", "GUNICORN_TIMEOUT",
    "GUNICORN_GRACEFUL_TIMEOUT", "GUNICORN_KEEP_ALIVE", "GUNICORN_MAX_REQUESTS",
    "GUNICORN_MAX_REQUESTS_JITTER", "GUNICORN_ACCESS_LOG", "DB_CONN_MAX_AGE",
    "DB_CONN_HEALTH_CHECKS", "REALTIME_TICKET_TTL_SECONDS", "REALTIME_PRESENCE_TTL_SECONDS",
    "REALTIME_HEARTBEAT_SECONDS", "REALTIME_OUTBOX_BATCH_SIZE",
    "REALTIME_OUTBOX_POLL_INTERVAL_SECONDS", "MYNA_PROFILE_DIRECT_SEND",
    "MYNA_GTHREAD_QUEUE_WRITER_BATCH_SIZE",
}
for key in identity_keys:
    if identity.get(key):
        result[key] = identity[key]
for key in messenger_keys:
    if messenger.get(key):
        result[key] = messenger[key]

if identity.get("CLOUDINARY_FOLDER"):
    result["IDENTITY_CLOUDINARY_FOLDER"] = identity["CLOUDINARY_FOLDER"]
if messenger.get("CLOUDINARY_FOLDER"):
    result["MESSENGER_CLOUDINARY_FOLDER"] = messenger["CLOUDINARY_FOLDER"]
if not result.get("CLOUDINARY_URL") and messenger.get("CLOUDINARY_URL"):
    result["CLOUDINARY_URL"] = messenger["CLOUDINARY_URL"]

jwt_secret = identity.get("JWT_SECRET_KEY") or messenger.get("JWT_VERIFYING_KEY")
if jwt_secret:
    result["JWT_SECRET_KEY"] = jwt_secret

internal_secret = (
    identity.get("MESSENGER_INTERNAL_SECRET")
    or messenger.get("MESSENGER_INTERNAL_SECRET")
    or messenger.get("CONTACT_POLICY_SYNC_SECRET")
)
if internal_secret:
    result["MESSENGER_INTERNAL_SECRET"] = internal_secret

result["IDENTITY_POSTGRES_DB"] = "myna_identity"
result["IDENTITY_POSTGRES_USER"] = "myna_identity"
result["IDENTITY_POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
result["MESSENGER_POSTGRES_DB"] = "myna_messenger"
result["MESSENGER_POSTGRES_USER"] = "myna_messenger"
result["MESSENGER_POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)

identity_user = quote(result["IDENTITY_POSTGRES_USER"], safe="")
identity_password = quote(result["IDENTITY_POSTGRES_PASSWORD"], safe="")
identity_db = quote(result["IDENTITY_POSTGRES_DB"], safe="")
messenger_user = quote(result["MESSENGER_POSTGRES_USER"], safe="")
messenger_password = quote(result["MESSENGER_POSTGRES_PASSWORD"], safe="")
messenger_db = quote(result["MESSENGER_POSTGRES_DB"], safe="")

result["IDENTITY_DATABASE_URL"] = (
    f"postgresql+psycopg://{identity_user}:{identity_password}"
    f"@identity-postgres:5432/{identity_db}"
)
result["MESSENGER_DATABASE_URL"] = (
    f"postgresql://{messenger_user}:{messenger_password}"
    f"@messenger-postgres:5432/{messenger_db}"
)

result["REDIS_PASSWORD"] = secrets.token_urlsafe(32)
encoded_redis = quote(result["REDIS_PASSWORD"], safe="")
result["REDIS_URL"] = f"redis://:{encoded_redis}@redis:6379/0"
result["CACHE_REDIS_URL"] = f"redis://:{encoded_redis}@redis:6379/1"

for key in ("SECRET_KEY", "JWT_SECRET_KEY", "DJANGO_SECRET_KEY", "MESSENGER_INTERNAL_SECRET"):
    if not result.get(key) or result[key] == "change-me":
        result[key] = secrets.token_urlsafe(64)

output_lines: list[str] = []
for raw in example.read_text(encoding="utf-8").splitlines():
    if not raw or raw.lstrip().startswith("#") or "=" not in raw:
        output_lines.append(raw)
        continue
    key = raw.split("=", 1)[0].strip()
    output_lines.append(f"{key}={result.get(key, '')}")

out.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
out.chmod(0o600)

print(f"Created {out}")
print("Created separate Identity and Messenger PostgreSQL credentials.")
print("Docker DNS hosts: identity-postgres and messenger-postgres.")
print("Migrated available legacy application secrets without printing secret values.")
print("Old MySQL data was not imported into PostgreSQL.")
PY
