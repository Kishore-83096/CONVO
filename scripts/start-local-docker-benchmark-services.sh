#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--root PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"

network_name="myna-local"
identity_image="identity-service-local:dev"
messenger_image="messenger-service-local:dev"
identity_container="identity-service-local"
messenger_container="messenger-service-local"
redis_container="redis"
identity_env_file="identity_service/.env.docker.local"
messenger_env_file="messenger/.env.benchmark.local"

info "Starting Myna local Docker BENCHMARK services"
require_file "$identity_env_file"
require_file "$messenger_env_file"
ensure_network "$network_name"

remove_container_if_exists "$messenger_container"
remove_container_if_exists "$identity_container"
remove_container_if_exists "$redis_container"

info "Starting Redis"
docker run -d --name "$redis_container" --network "$network_name" -p 6379:6379 redis:7-alpine >/dev/null

info "Building Identity image"
docker build -t "$identity_image" ./identity_service

info "Starting Identity"
docker run -d --name "$identity_container" --network "$network_name" --env-file "$identity_env_file" -p 5000:5000 "$identity_image" >/dev/null
wait_http_ok "Identity" "http://127.0.0.1:5000/api/v1/health/" 15 || {
  docker logs --tail 200 "$identity_container" || true
  exit 1
}

info "Building Messenger image"
docker build -t "$messenger_image" ./messenger

info "Starting Messenger in BENCHMARK mode"
docker run -d --name "$messenger_container" --network "$network_name" --env-file "$messenger_env_file" -p 8000:8000 "$messenger_image" >/dev/null
wait_http_ok "Messenger" "http://127.0.0.1:8000/api/v1/health/" 15 || {
  docker logs --tail 250 "$messenger_container" || true
  exit 1
}

info "Verifying benchmark env inside Messenger container"
docker exec "$messenger_container" python -c "import os; keys=['DJANGO_DEBUG','DB_CONN_MAX_AGE','WEB_CONCURRENCY','ASGI_THREADS','GUNICORN_BACKLOG','GUNICORN_TIMEOUT','GUNICORN_GRACEFUL_TIMEOUT','GUNICORN_KEEP_ALIVE','MYNA_PROFILE_DIRECT_SEND','GUNICORN_ACCESS_LOG']; [print(k+'='+str(os.getenv(k,''))) for k in keys]"

info "Verifying benchmark env inside Identity container"
docker exec "$identity_container" python -c "import os; keys=['WEB_CONCURRENCY','GUNICORN_THREADS','GUNICORN_BACKLOG','GUNICORN_TIMEOUT','GUNICORN_GRACEFUL_TIMEOUT','GUNICORN_KEEP_ALIVE']; [print(k+'='+str(os.getenv(k,''))) for k in keys]"

info "Container status"
docker ps --filter "name=identity-service-local" --filter "name=messenger-service-local" --filter "name=redis" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

pass "Myna local Docker BENCHMARK services started successfully"
printf '\nSafe benchmark command:\n  ./scripts/run-local-docker-benchmark.sh\n'
printf '\nFull benchmark command:\n  ./scripts/run-local-docker-benchmark.sh --runner-env-file messenger/.env.benchmark.runner.full.local\n'
