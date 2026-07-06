#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
runner_env_file="messenger/.env.benchmark.runner.docker-network.local"
identity_env_file="identity_service/env/identity.benchmark.env"
messenger_env_file="messenger/env/messenger.benchmark.env"
report_dir="benchmark/myna_api_test_reports"
docker_stats_interval_ms=1000
stop_on_run_failure=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --runner-env-file) runner_env_file="$2"; shift 2 ;;
    --identity-env-file) identity_env_file="$2"; shift 2 ;;
    --messenger-env-file) messenger_env_file="$2"; shift 2 ;;
    --report-dir) report_dir="$2"; shift 2 ;;
    --docker-stats-interval-milliseconds) docker_stats_interval_ms="$2"; shift 2 ;;
    --stop-on-run-failure) stop_on_run_failure=1; shift ;;
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
metadata_dir="$resolved_report_dir/server_mode_comparison_$stamp"
mkdir -p "$metadata_dir"

common_runner=(MYNA_BENCHMARK_LEVELS=1,5,10,20,30,40,50,60,70,80,90,100 MYNA_DISTRIBUTED_PAIR_COUNT=100 MYNA_WARMUP_ALL_PAIRS=true MYNA_CONNECTION_WARMUP_ENABLED=true MYNA_CONNECTION_WARMUP_CONCURRENCY=100 MYNA_HTTP_MAX_CONNECTIONS=300 MYNA_HTTP_MAX_KEEPALIVE_CONNECTIONS=300 MYNA_HTTP_KEEPALIVE_EXPIRY_SECONDS=60 MYNA_HTTP_POOL_TIMEOUT_SECONDS=10 MYNA_BENCHMARK_COOLDOWN_SECONDS=3 MYNA_REQUEST_TIMEOUT_SECONDS=30 MYNA_STOP_ON_FIRST_FAILED_LEVEL=false MYNA_CLEANUP_MESSENGER_DJANGO=true MYNA_CLEANUP_IDENTITY_USERS=true MYNA_RUNNER_PATH=docker-network)
common_messenger=(MESSENGER_PROCESS_ROLE=http GUNICORN_BACKLOG=4096 GUNICORN_TIMEOUT=60 GUNICORN_GRACEFUL_TIMEOUT=30 GUNICORN_KEEP_ALIVE=5)
configs=("A|ASGI baseline|asgi|5|8|" "B|ASGI increased threads|asgi|5|16|" "C|ASGI increased workers|asgi|8|16|" "D|WSGI gthread baseline|wsgi|4||8" "E|WSGI gthread balanced|wsgi|5||8" "F|WSGI gthread high threads|wsgi|5||12")
metadata_paths=()

for config in "${configs[@]}"; do
  IFS='|' read -r id label mode web asgi_threads gunicorn_threads <<<"$config"
  slug="$(printf '%s_%s' "$id" "$label" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_|_$//g')"
  metadata_path="$metadata_dir/${slug}.run.json"
  metadata_paths+=("$metadata_path")
  test_run_id="myna-smc-$(printf '%s' "$stamp" | tr -cd '[:alnum:]')-$(printf '%s' "$id" | tr '[:upper:]' '[:lower:]')"
  messenger_env=("MESSENGER_HTTP_SERVER_MODE=$mode" "WEB_CONCURRENCY=$web")
  [[ -n "$asgi_threads" ]] && messenger_env+=("ASGI_THREADS=$asgi_threads")
  [[ -n "$gunicorn_threads" ]] && messenger_env+=("GUNICORN_THREADS=$gunicorn_threads")
  messenger_env+=("${common_messenger[@]}")
  runner_env=("MYNA_REPORT_FILE_PREFIX=myna_server_mode_$slug" "MYNA_TEST_RUN_ID=$test_run_id" "${common_runner[@]}")
  args=(--root "$PWD" --runner-env-file "$runner_env_file" --identity-env-file "$identity_env_file" --messenger-env-file "$messenger_env_file" --report-dir "$report_dir" --docker-stats-interval-milliseconds "$docker_stats_interval_ms" --run-label "$id. $label" --run-metadata-output-path "$metadata_path")
  for item in "${messenger_env[@]}"; do args+=(--messenger-env "$item"); done
  for item in "${runner_env[@]}"; do args+=(--runner-env "$item"); done
  info "Running $id. $label"
  if ! "$PWD/scripts/run-local-docker-network-benchmark-accurate-timing.sh" "${args[@]}"; then
    warn "Run failed: $id. $label"
    [[ "$stop_on_run_failure" -eq 1 ]] && exit 1
  fi
done

manifest_path="$metadata_dir/server_mode_comparison_runs.json"
python3 - "$manifest_path" "${metadata_paths[@]}" <<'PY'
import datetime, json, sys
runs = []
for path in sys.argv[2:]:
    try:
        runs.append(json.load(open(path, encoding="utf-8")))
    except FileNotFoundError:
        runs.append({"benchmark_succeeded": False, "benchmark_error": f"Missing metadata: {path}"})
json.dump({"created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "report_type": "server_mode_comparison", "runs": runs}, open(sys.argv[1], "w", encoding="utf-8"), indent=2)
PY
combined_report_path="$resolved_report_dir/server_mode_comparison_$stamp.md"
python3 ./scripts/build-server-mode-comparison-report.py --runs-manifest "$manifest_path" --output-md "$combined_report_path"
pass "Server-mode comparison complete"
printf '  Combined report: %s\n  Run manifest:    %s\n' "$combined_report_path" "$manifest_path"
