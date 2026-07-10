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
[[ -f compose.yml ]] || { echo "compose.yml is missing" >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo "Docker CLI is required" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "Docker daemon is not available" >&2; exit 2; }

if grep -q '=change-me' .env; then
  echo ".env still contains one or more change-me placeholders." >&2
  exit 2
fi

if grep -Eq '^(MYSQL_|IDENTITY_DATABASE_URL=.*@mysql:|MESSENGER_DATABASE_URL=.*@mysql:)' .env; then
  echo "The root .env still contains the old local MySQL configuration." >&2
  echo "Run: bash ./scripts/update-env-to-postgres.sh" >&2
  exit 2
fi

required=(
  IDENTITY_POSTGRES_DB
  IDENTITY_POSTGRES_USER
  IDENTITY_POSTGRES_PASSWORD
  MESSENGER_POSTGRES_DB
  MESSENGER_POSTGRES_USER
  MESSENGER_POSTGRES_PASSWORD
  IDENTITY_DATABASE_URL
  MESSENGER_DATABASE_URL
  REDIS_PASSWORD
  SECRET_KEY
  JWT_SECRET_KEY
  DJANGO_SECRET_KEY
  MESSENGER_INTERNAL_SECRET
)
for key in "${required[@]}"; do
  value="$(sed -n "s/^${key}=//p" .env | tail -1)"
  [[ -n "$value" ]] || { echo "Missing required .env value: $key" >&2; exit 2; }
done

identity_database_url="$(sed -n 's/^IDENTITY_DATABASE_URL=//p' .env | tail -1)"
messenger_database_url="$(sed -n 's/^MESSENGER_DATABASE_URL=//p' .env | tail -1)"
[[ "$identity_database_url" == *"@identity-postgres:5432/"* ]] || {
  echo "IDENTITY_DATABASE_URL must use Docker DNS host identity-postgres:5432" >&2
  exit 2
}
[[ "$messenger_database_url" == *"@messenger-postgres:5432/"* ]] || {
  echo "MESSENGER_DATABASE_URL must use Docker DNS host messenger-postgres:5432" >&2
  exit 2
}

legacy_containers=(
  identity-service-local
  messenger-service-local
  messenger-outbox-local
  mysql-benchmark-local
  myna-benchmark-runner
  myna-benchmark-runner-precheck
  myna-accurate-timing-benchmark
  redis
)

# A manually-created historical myna-local network causes Compose ownership-label
# errors. Remove known legacy Myna endpoints first. If an unknown endpoint remains,
# fail rather than deleting an unrelated container.
if docker network inspect myna-local >/dev/null 2>&1; then
  compose_network_label="$(
    docker network inspect \
      --format '{{index .Labels "com.docker.compose.network"}}' \
      myna-local 2>/dev/null || true
  )"
  if [[ "$compose_network_label" != "myna-local" ]]; then
    echo "==> Repairing legacy manually-created myna-local Docker network"
    for container in "${legacy_containers[@]}"; do
      docker inspect "$container" >/dev/null 2>&1 || continue
      networks="$(
        docker inspect \
          --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' \
          "$container" 2>/dev/null || true
      )"
      if [[ " $networks " == *" myna-local "* ]]; then
        echo "==> Removing legacy Myna container: $container (volumes preserved)"
        docker rm -f "$container" >/dev/null
      fi
    done

    remaining_endpoints="$(
      docker network inspect \
        --format '{{range $id, $container := .Containers}}{{$container.Name}} {{end}}' \
        myna-local 2>/dev/null || true
    )"
    if [[ -n "${remaining_endpoints// }" ]]; then
      echo "Cannot replace legacy myna-local network because unknown endpoint(s) remain:" >&2
      echo "$remaining_endpoints" >&2
      exit 1
    fi
    docker network rm myna-local >/dev/null
  fi
fi

echo "==> Stopping the existing Myna Compose project (volumes preserved)"
docker compose --env-file .env -f compose.yml down --remove-orphans

# Retire only known legacy Myna containers that can conflict with the canonical
# Compose stack. Generic names such as redis are removed only when attached to
# the historical myna-local network. No volumes or unrelated containers are touched.
for container in "${legacy_containers[@]}"; do
  docker inspect "$container" >/dev/null 2>&1 || continue
  networks="$(
    docker inspect \
      --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' \
      "$container" 2>/dev/null || true
  )"
  if [[ "$container" == "redis" && " $networks " != *" myna-local "* ]]; then
    echo "==> Leaving unrelated container named redis untouched"
    continue
  fi
  echo "==> Removing legacy Myna container: $container (volumes preserved)"
  docker rm -f "$container" >/dev/null
done

echo "==> Building Myna application images once"
docker compose --env-file .env -f compose.yml build identity messenger

echo "==> Starting separate PostgreSQL databases and shared Redis"
docker compose --env-file .env -f compose.yml up -d \
  identity-postgres messenger-postgres redis

echo "==> Running the one-shot Identity migration service"
docker compose --env-file .env -f compose.yml run --rm identity-migrate

echo "==> Running the one-shot Messenger migration service"
docker compose --env-file .env -f compose.yml run --rm messenger-migrate

echo "==> Starting Identity, Messenger HTTP, and Messenger outbox"
docker compose --env-file .env -f compose.yml up -d \
  identity messenger messenger-outbox

echo "==> Waiting for service health"
for service in identity messenger; do
  healthy=false
  status="missing"
  for _ in $(seq 1 60); do
    id="$(docker compose --env-file .env -f compose.yml ps -q "$service")"
    if [[ -n "$id" ]]; then
      status="$(
        docker inspect \
          --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
          "$id" 2>/dev/null || true
      )"
      if [[ "$status" == "healthy" ]]; then
        healthy=true
        break
      fi
    fi
    sleep 2
  done
  if [[ "$healthy" != true ]]; then
    docker compose --env-file .env -f compose.yml logs --tail 100 "$service" || true
    echo "$service is not healthy: $status" >&2
    exit 1
  fi
done

echo
docker compose --env-file .env -f compose.yml ps
echo
echo "Identity:  http://localhost:5000"
echo "Messenger: http://localhost:8000"
echo "Identity DB DNS:  identity-postgres:5432"
echo "Messenger DB DNS: messenger-postgres:5432"
