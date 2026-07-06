#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
runner_env_file="messenger/.env.benchmark.runner.docker-network.local"
messenger_env_file="messenger/.env.benchmark.local"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --runner-env-file) runner_env_file="$2"; shift 2 ;;
    --messenger-env-file) messenger_env_file="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--root PATH] [--runner-env-file PATH] [--messenger-env-file PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"

network_name="myna-local"
runner_container="myna-benchmark-runner"
precheck_container="myna-benchmark-runner-precheck"
base_messenger_image="messenger-service-local:dev"
benchmark_runner_image="messenger-benchmark-runner-local:dev"

info "Running benchmark INSIDE Docker network"
require_file "$runner_env_file"
require_file "$messenger_env_file"
require_file "messenger/Dockerfile.benchmark-runner"
require_file "messenger/requirements-benchmark.txt"
require_dir "messenger/api_tests"
mkdir -p benchmark

[[ "$(docker network ls --format '{{.Name}}' | awk -v n="$network_name" '$0 == n { print }')" == "$network_name" ]] || die "Docker network not found: $network_name. Start benchmark services first."
for container in identity-service-local messenger-service-local redis; do
  container_running "$container" || die "Required container is not running: $container. Run start-local-docker-benchmark-services.sh first."
  pass "Container running: $container"
done

docker images --format '{{.Repository}}:{{.Tag}}' | grep -Fxq "$base_messenger_image" || die "Base Messenger image not found: $base_messenger_image. Run start-local-docker-benchmark-services.sh first."

info "Building clean benchmark runner image"
docker build -t "$benchmark_runner_image" -f ./messenger/Dockerfile.benchmark-runner ./messenger

remove_container_if_exists "$runner_container"
remove_container_if_exists "$precheck_container"

benchmark_path="$(abs_path benchmark)"
api_tests_path="$(abs_path messenger/api_tests)"
env_path="$(abs_path "$runner_env_file")"
host_user_args=(--user "$(id -u):$(id -g)" -e PYTHONDONTWRITEBYTECODE=1)
cleanup_database_url="$(dotenv_get "$messenger_env_file" DATABASE_URL || true)"
if [[ -n "$cleanup_database_url" ]]; then
  cleanup_database_url="${cleanup_database_url//@127.0.0.1:/@host.docker.internal:}"
  cleanup_database_url="${cleanup_database_url//@localhost:/@host.docker.internal:}"
fi
cleanup_database_env_args=()
if [[ -n "$cleanup_database_url" ]]; then
  cleanup_database_env_args=(-e "DATABASE_URL=$cleanup_database_url")
fi

info "Testing Docker DNS from benchmark runner container"
docker run --rm --name "$precheck_container" --network "$network_name" --env-file "$env_path" --add-host=host.docker.internal:host-gateway \
  "${host_user_args[@]}" \
  -v "${benchmark_path}:/reports" "$benchmark_runner_image" \
  -c "import urllib.request; print(urllib.request.urlopen('http://identity-service-local:5000/api/v1/health/', timeout=10).read().decode()); print(urllib.request.urlopen('http://messenger-service-local:8000/api/v1/health/', timeout=10).read().decode())"

info "Starting Docker-network benchmark runner"
docker run --rm --name "$runner_container" --network "$network_name" --env-file "$env_path" --add-host=host.docker.internal:host-gateway \
  "${host_user_args[@]}" \
  -e MYNA_CLEANUP_MESSENGER_DJANGO=true \
  -e MYNA_MESSENGER_DOCKER_CONTAINER= \
  "${cleanup_database_env_args[@]}" \
  -v "${benchmark_path}:/reports" \
  -v "${api_tests_path}:/app/api_tests:ro" \
  "$benchmark_runner_image" /app/api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py

pass "Docker-network benchmark completed"
info "Latest reports"
find benchmark/myna_api_test_reports -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM %s %f\n' 2>/dev/null | sort -r | head -10 || true
