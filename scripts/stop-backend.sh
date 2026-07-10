#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"
[[ -f .env ]] || { echo "Missing .env" >&2; exit 2; }
docker compose --env-file .env -f compose.yml down --remove-orphans
echo "Myna backend stopped. Named volumes were preserved."
