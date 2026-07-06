#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
runner_env_file="messenger/.env.benchmark.runner.docker-network.local"
identity_env_file="identity_service/env/identity.benchmark.env"
messenger_env_file="messenger/env/messenger.benchmark.env"
report_dir="benchmark/myna_api_test_reports"
mode="asgi"
web_concurrency="5"
asgi_threads="8"
gunicorn_threads=""
docker_stats_interval_ms=1000

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --runner-env-file) runner_env_file="$2"; shift 2 ;;
    --identity-env-file) identity_env_file="$2"; shift 2 ;;
    --messenger-env-file) messenger_env_file="$2"; shift 2 ;;
    --report-dir) report_dir="$2"; shift 2 ;;
    --messenger-http-server-mode) mode="$2"; shift 2 ;;
    --web-concurrency) web_concurrency="$2"; shift 2 ;;
    --asgi-threads) asgi_threads="$2"; shift 2 ;;
    --gunicorn-threads) gunicorn_threads="$2"; shift 2 ;;
    --docker-stats-interval-milliseconds) docker_stats_interval_ms="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [options]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"
[[ -f "$identity_env_file" ]] || identity_env_file="identity_service/.env.benchmark.mysql-docker.local"
[[ -f "$messenger_env_file" ]] || messenger_env_file="messenger/.env.benchmark.mysql-docker.local"
resolved_report_dir="$(abs_path "$report_dir")"
mkdir -p "$resolved_report_dir"
stamp="$(date +%H-%M-%S_%Y-%m-%d)"
metadata_path="$resolved_report_dir/endpoint_gap_comparison_${stamp}.run.json"
endpoint_report_path="$resolved_report_dir/endpoint_gap_comparison_${stamp}.md"
test_run_id="myna-endpoint-$(printf '%s' "$stamp" | tr -cd '[:alnum:]')"

messenger_env=(MESSENGER_PROCESS_ROLE=http "MESSENGER_HTTP_SERVER_MODE=$mode" "WEB_CONCURRENCY=$web_concurrency" GUNICORN_BACKLOG=4096 GUNICORN_TIMEOUT=60 GUNICORN_GRACEFUL_TIMEOUT=30 GUNICORN_KEEP_ALIVE=5)
if [[ "$mode" == "asgi" && -n "$asgi_threads" ]]; then messenger_env+=("ASGI_THREADS=$asgi_threads"); fi
if [[ "$mode" == "wsgi" ]]; then messenger_env+=("GUNICORN_THREADS=${gunicorn_threads:-8}"); fi
runner_env=(MYNA_REPORT_FILE_PREFIX=myna_endpoint_gap_comparison "MYNA_TEST_RUN_ID=$test_run_id" MYNA_ENDPOINT_BENCHMARK_LEVELS=1,5,10,20,30,40,50,60,70,80,90,100 MYNA_ENDPOINT_BENCHMARK_REQUESTS_PER_LEVEL=100 MYNA_DISTRIBUTED_PAIR_COUNT=100 MYNA_WARMUP_ALL_PAIRS=true MYNA_HTTP_MAX_CONNECTIONS=300 MYNA_HTTP_MAX_KEEPALIVE_CONNECTIONS=300 MYNA_HTTP_KEEPALIVE_EXPIRY_SECONDS=60 MYNA_HTTP_POOL_TIMEOUT_SECONDS=10 MYNA_BENCHMARK_COOLDOWN_SECONDS=3 MYNA_REQUEST_TIMEOUT_SECONDS=30 MYNA_STOP_ON_FIRST_FAILED_LEVEL=false MYNA_CLEANUP_MESSENGER_DJANGO=true MYNA_CLEANUP_IDENTITY_USERS=true MYNA_RUNNER_PATH=docker-network)

args=(--root "$PWD" --runner-env-file "$runner_env_file" --identity-env-file "$identity_env_file" --messenger-env-file "$messenger_env_file" --report-dir "$report_dir" --docker-stats-interval-milliseconds "$docker_stats_interval_ms" --benchmark-script "/app/api_tests/full_api_flow/myna_endpoint_gap_comparison_benchmark.py" --run-label "Endpoint gap comparison" --run-metadata-output-path "$metadata_path")
for item in "${messenger_env[@]}"; do args+=(--messenger-env "$item"); done
for item in "${runner_env[@]}"; do args+=(--runner-env "$item"); done

info "Starting Docker-network endpoint gap comparison"
run_error=""
"$PWD/scripts/run-local-docker-network-benchmark-accurate-timing.sh" "${args[@]}" || run_error="benchmark wrapper reported failure"

require_file "$metadata_path"
json_report_path="$(python3 - "$metadata_path" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("json_report_path") or "")
PY
)"
[[ -n "$json_report_path" ]] || die "Endpoint benchmark did not produce a JSON report. Last error: $run_error"
python3 ./scripts/build-endpoint-gap-comparison-report.py --json-report "$json_report_path" --output-md "$endpoint_report_path"
pass "Endpoint gap comparison complete"
printf '  JSON report:     %s\n  Endpoint report: %s\n' "$json_report_path" "$endpoint_report_path"
