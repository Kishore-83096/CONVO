#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
runner_env_file="messenger/.env.benchmark.runner.local"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --runner-env-file) runner_env_file="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--root PATH] [--runner-env-file PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"
resolved_env_file="$(abs_path "$runner_env_file")"

info "Loading benchmark runner env"
load_dotenv "$resolved_env_file"
pass "Loaded env file: $resolved_env_file"

info "Checking required benchmark env values"
for key in MYNA_SERVICE_URL_MODE MYNA_DOCKER_IDENTITY_BASE_URL MYNA_DOCKER_MESSENGER_BASE_URL MYNA_BENCHMARK_LEVELS MYNA_DISTRIBUTED_PAIR_COUNT MYNA_REPORT_ROOT MYNA_MESSENGER_PROJECT_ROOT; do
  value="${!key:-}"
  [[ -n "${value//[[:space:]]/}" ]] || die "Missing required benchmark env value: $key"
  case "$key" in
    *SECRET*|*KEY*|*TOKEN*|*PASSWORD*) pass "$key is set" ;;
    *) pass "$key=$value" ;;
  esac
done

info "Checking Docker containers"
for container in "${MYNA_IDENTITY_DOCKER_CONTAINER:-}" "${MYNA_MESSENGER_DOCKER_CONTAINER:-}" "${MYNA_REDIS_DOCKER_CONTAINER:-}"; do
  [[ -z "$container" ]] && continue
  container_running "$container" || die "Required container is not running: $container"
  pass "Container running: $container"
done

info "Checking service health through host ports"
identity_base_url="${MYNA_DOCKER_IDENTITY_BASE_URL%/}"
messenger_base_url="${MYNA_DOCKER_MESSENGER_BASE_URL%/}"
wait_http_ok "Identity health" "$identity_base_url/api/v1/health/" 1
wait_http_ok "Messenger health" "$messenger_base_url/api/v1/health/" 1

info "Checking Python benchmark dependencies"
messenger_root="$PWD/messenger"
python_bin="$(python_cmd_for_messenger "$messenger_root")"
pass "Using Python: $python_bin"
for module in httpx cryptography; do
  "$python_bin" -c "import $module" >/dev/null 2>&1 || die "Missing Python module: $module. Install it in messenger venv, then retry."
  pass "Python module available: $module"
done

info "Preparing report folder"
mkdir -p "$MYNA_REPORT_ROOT"
pass "Report root exists: $MYNA_REPORT_ROOT"

info "Running benchmark"
cd "$messenger_root"
benchmark_file="api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py"
require_file "$benchmark_file"
printf '\nBenchmark command:\n%s %s\n\n' "$python_bin" "$benchmark_file"
"$python_bin" "$benchmark_file"

cd "$root"
pass "Benchmark completed successfully"

info "Latest reports"
report_dir="$MYNA_REPORT_ROOT/myna_api_test_reports"
if [[ -d "$report_dir" ]]; then
  find "$report_dir" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM %s %f\n' | sort -r | head -10
else
  warn "Report directory not found yet: $report_dir"
fi

pass "Sprint 3 Phase 3.3 completed successfully"
