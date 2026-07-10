#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

[[ -f .env ]] || {
  echo "Missing $repo_root/.env" >&2
  echo "Run: bash ./scripts/migrate-env-to-root.sh" >&2
  exit 2
}
[[ -f .env.example ]] || { echo ".env.example is missing" >&2; exit 2; }

python3 - "$repo_root" <<'PY'
from __future__ import annotations

import secrets
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

root = Path(sys.argv[1])
env_path = root / ".env"
example_path = root / ".env.example"


def parse_env(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
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


current = parse_env(env_path)
example = parse_env(example_path)
result = dict(example)
result.update(current)

mysql_keys = {
    "MYSQL_ROOT_PASSWORD",
    "MYSQL_APP_USER",
    "MYSQL_APP_PASSWORD",
    "MYSQL_IDENTITY_DATABASE",
    "MYSQL_MESSENGER_DATABASE",
}
for key in mysql_keys:
    result.pop(key, None)

result["IDENTITY_POSTGRES_DB"] = (
    current.get("IDENTITY_POSTGRES_DB") or "myna_identity"
)
result["IDENTITY_POSTGRES_USER"] = (
    current.get("IDENTITY_POSTGRES_USER") or "myna_identity"
)
identity_password = current.get("IDENTITY_POSTGRES_PASSWORD", "")
if not identity_password or identity_password == "change-me":
    identity_password = secrets.token_urlsafe(32)
result["IDENTITY_POSTGRES_PASSWORD"] = identity_password

result["MESSENGER_POSTGRES_DB"] = (
    current.get("MESSENGER_POSTGRES_DB") or "myna_messenger"
)
result["MESSENGER_POSTGRES_USER"] = (
    current.get("MESSENGER_POSTGRES_USER") or "myna_messenger"
)
messenger_password = current.get("MESSENGER_POSTGRES_PASSWORD", "")
if not messenger_password or messenger_password == "change-me":
    messenger_password = secrets.token_urlsafe(32)
result["MESSENGER_POSTGRES_PASSWORD"] = messenger_password

identity_user = quote(result["IDENTITY_POSTGRES_USER"], safe="")
identity_password_encoded = quote(result["IDENTITY_POSTGRES_PASSWORD"], safe="")
identity_db = quote(result["IDENTITY_POSTGRES_DB"], safe="")
messenger_user = quote(result["MESSENGER_POSTGRES_USER"], safe="")
messenger_password_encoded = quote(result["MESSENGER_POSTGRES_PASSWORD"], safe="")
messenger_db = quote(result["MESSENGER_POSTGRES_DB"], safe="")

result["IDENTITY_DATABASE_URL"] = (
    f"postgresql+psycopg://{identity_user}:{identity_password_encoded}"
    f"@identity-postgres:5432/{identity_db}"
)
result["MESSENGER_DATABASE_URL"] = (
    f"postgresql://{messenger_user}:{messenger_password_encoded}"
    f"@messenger-postgres:5432/{messenger_db}"
)

known_keys: list[str] = []
output_lines: list[str] = []
for raw in example_path.read_text(encoding="utf-8").splitlines():
    if not raw or raw.lstrip().startswith("#") or "=" not in raw:
        output_lines.append(raw)
        continue
    key = raw.split("=", 1)[0].strip()
    known_keys.append(key)
    output_lines.append(f"{key}={result.get(key, '')}")

preserved_custom = [
    key
    for key in current
    if key not in known_keys and key not in mysql_keys
]
if preserved_custom:
    output_lines.extend(
        [
            "",
            "# Preserved custom variables from the previous root .env",
        ]
    )
    for key in sorted(preserved_custom):
        output_lines.append(f"{key}={current[key]}")

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = root / f".env.before-postgres-{stamp}.bak"
backup.write_bytes(env_path.read_bytes())
backup.chmod(0o600)

temp = root / ".env.postgres.tmp"
temp.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
temp.chmod(0o600)
temp.replace(env_path)
env_path.chmod(0o600)

print(f"Updated {env_path}")
print(f"Backup: {backup}")
print("Identity database DNS host: identity-postgres")
print("Messenger database DNS host: messenger-postgres")
print("Generated separate PostgreSQL passwords where missing.")
print("Old MySQL data was not migrated into PostgreSQL.")
PY
