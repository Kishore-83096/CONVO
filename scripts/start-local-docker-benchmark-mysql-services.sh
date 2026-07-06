#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
root_password="benchmark_root_password"
benchmark_user="myna_benchmark"
benchmark_password="myna_benchmark_password"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --benchmark-mysql-root-password) root_password="$2"; shift 2 ;;
    --benchmark-mysql-user) benchmark_user="$2"; shift 2 ;;
    --benchmark-mysql-password) benchmark_password="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--root PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"

network_name="myna-local"
mysql_container="mysql-benchmark-local"
mysql_image="mysql:8.4"
redis_container="redis"
identity_container="identity-service-local"
messenger_container="messenger-service-local"
identity_image="identity-service-local:dev"
messenger_image="messenger-service-local:dev"
identity_env="identity_service/.env.benchmark.mysql-docker.local"
messenger_env="messenger/.env.benchmark.mysql-docker.local"

info "Starting Docker-MySQL benchmark services"
require_file "$identity_env"
require_file "$messenger_env"
ensure_network "$network_name"

info "Ensuring benchmark MySQL is running"
if container_running "$mysql_container"; then
  pass "MySQL benchmark container is running"
elif container_exists "$mysql_container"; then
  docker start "$mysql_container" >/dev/null
  pass "Started existing MySQL benchmark container"
else
  docker run -d \
    --name "$mysql_container" \
    --network "$network_name" \
    -e "MYSQL_ROOT_PASSWORD=$root_password" \
    -p 3306:3306 \
    "$mysql_image" >/dev/null
  pass "Created MySQL benchmark container"
fi
wait_mysql_ready "$mysql_container" "$root_password"
repair_benchmark_mysql_grants "$mysql_container" "$root_password" "$benchmark_user" "$benchmark_password"

info "Ensuring Redis is running"
if ! container_running "$redis_container"; then
  remove_container_if_exists "$redis_container"
  docker run -d --name "$redis_container" --network "$network_name" -p 6379:6379 redis:7-alpine >/dev/null
  pass "Started Redis container"
else
  warn "Redis already running"
fi

info "Stopping old Identity and Messenger containers"
remove_container_if_exists "$identity_container"
remove_container_if_exists "$messenger_container"

info "Building Identity image"
docker build -t "$identity_image" ./identity_service

info "Building Messenger image"
docker build -t "$messenger_image" ./messenger

info "Starting Identity with Docker MySQL env"
docker run -d --name "$identity_container" --network "$network_name" --env-file "$identity_env" -p 5000:5000 "$identity_image" >/dev/null

info "Starting Messenger with Docker MySQL env"
docker run -d --name "$messenger_container" --network "$network_name" --env-file "$messenger_env" -p 8000:8000 "$messenger_image" >/dev/null

if ! wait_http_ok "Identity" "http://127.0.0.1:5000/api/v1/health/"; then
  docker logs "$identity_container" --tail 120 || true
  exit 1
fi
if ! wait_http_ok "Messenger" "http://127.0.0.1:8000/api/v1/health/"; then
  docker logs "$messenger_container" --tail 120 || true
  exit 1
fi

info "Verifying Docker-MySQL benchmark env inside Identity container"
docker exec "$identity_container" python -c "import os; keys=['WEB_CONCURRENCY','GUNICORN_THREADS','GUNICORN_BACKLOG','GUNICORN_TIMEOUT','GUNICORN_GRACEFUL_TIMEOUT','GUNICORN_KEEP_ALIVE']; [print(k+'='+str(os.getenv(k,''))) for k in keys]"

info "Verifying Docker-MySQL benchmark env inside Messenger container"
docker exec "$messenger_container" python -c "import os; keys=['WEB_CONCURRENCY','ASGI_THREADS','GUNICORN_BACKLOG','GUNICORN_TIMEOUT','GUNICORN_GRACEFUL_TIMEOUT','GUNICORN_KEEP_ALIVE','MESSENGER_PROCESS_ROLE','MESSENGER_HTTP_SERVER_MODE']; [print(k+'='+str(os.getenv(k,''))) for k in keys]"

pass "Docker-MySQL benchmark services are ready"
docker ps --filter "name=identity-service-local" --filter "name=messenger-service-local" --filter "name=mysql-benchmark-local" --filter "name=redis" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
