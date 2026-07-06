#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
runner_env_file="messenger/.env.benchmark.runner.docker-network.local"
identity_env_file="identity_service/env/identity.benchmark.env"
messenger_env_file="messenger/env/messenger.benchmark.env"
report_dir="benchmark/myna_api_test_reports"
docker_stats_interval_ms=1000
benchmark_script="/app/api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py"
run_label=""
run_metadata_output_path=""
root_password="benchmark_root_password"
benchmark_user="myna_benchmark"
benchmark_password="myna_benchmark_password"
outbox_worker_enabled="true"
outbox_drain_timeout_seconds=30
outbox_drain_poll_seconds=1
write_readme=true
cleanup_artifacts=true
messenger_env_args=()
outbox_env_args=()
runner_env_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --runner-env-file) runner_env_file="$2"; shift 2 ;;
    --identity-env-file) identity_env_file="$2"; shift 2 ;;
    --messenger-env-file) messenger_env_file="$2"; shift 2 ;;
    --report-dir) report_dir="$2"; shift 2 ;;
    --docker-stats-interval-milliseconds) docker_stats_interval_ms="$2"; shift 2 ;;
    --benchmark-script) benchmark_script="$2"; shift 2 ;;
    --messenger-env) messenger_env_args+=("$2"); shift 2 ;;
    --outbox-env) outbox_env_args+=("$2"); shift 2 ;;
    --runner-env) runner_env_args+=("$2"); shift 2 ;;
    --run-label) run_label="$2"; shift 2 ;;
    --run-metadata-output-path) run_metadata_output_path="$2"; shift 2 ;;
    --benchmark-mysql-root-password) root_password="$2"; shift 2 ;;
    --benchmark-mysql-user) benchmark_user="$2"; shift 2 ;;
    --benchmark-mysql-password) benchmark_password="$2"; shift 2 ;;
    --disable-outbox-worker) outbox_worker_enabled="false"; shift ;;
    --outbox-drain-timeout-seconds) outbox_drain_timeout_seconds="$2"; shift 2 ;;
    --outbox-drain-poll-seconds) outbox_drain_poll_seconds="$2"; shift 2 ;;
    --skip-readme) write_readme=false; shift ;;
    --keep-artifacts) cleanup_artifacts=false; shift ;;
    -h|--help) printf 'Usage: %s [options]\nUse --messenger-env KEY=VALUE, --outbox-env KEY=VALUE, and --runner-env KEY=VALUE repeatedly.\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"
[[ -f "$identity_env_file" ]] || identity_env_file="identity_service/.env.benchmark.mysql-docker.local"
[[ -f "$messenger_env_file" ]] || messenger_env_file="messenger/.env.benchmark.mysql-docker.local"
for path in "$runner_env_file" "$identity_env_file" "$messenger_env_file" messenger/Dockerfile.benchmark-runner messenger/requirements-benchmark.txt messenger/api_tests; do
  [[ -e "$path" ]] || die "Missing required path: $path"
done

network_name="myna-local"
mysql_container="mysql-benchmark-local"
redis_container="redis"
identity_container="identity-service-local"
messenger_container="messenger-service-local"
outbox_container="messenger-outbox-local"
identity_image="identity-service-local:dev"
messenger_image="messenger-service-local:dev"
runner_image="messenger-benchmark-runner-local:dev"
runner_container="myna-benchmark-runner"
precheck_container="myna-benchmark-runner-precheck"
gunicorn_log_container="/tmp/myna_benchmark_gunicorn_access.log"
exception_log_container="/tmp/myna_benchmark_asgi_exceptions.jsonl"
gunicorn_access_log_format='%(t)s pid=%(p)s status=%(s)s duration_us=%(D)s method="%(m)s" path="%(U)s" run="%({x-myna-benchmark-run-id}i)s" req="%({x-myna-benchmark-request-id}i)s" phase="%({x-myna-benchmark-phase}i)s" concurrency="%({x-myna-benchmark-concurrency}i)s"'

resolved_report_dir="$(abs_path "$report_dir")"
mkdir -p "$resolved_report_dir"
run_stamp="$(date +%H-%M-%S_%Y-%m-%d)"
run_artifact_dir="$resolved_report_dir/.${run_stamp}_accurate_timing_artifacts"
mkdir -p "$run_artifact_dir"
host_stats_csv="$run_artifact_dir/${run_stamp}_host_docker_stats.csv"
gunicorn_log_host="$run_artifact_dir/${run_stamp}_myna_benchmark_gunicorn_access.log"
exception_log_host="$run_artifact_dir/${run_stamp}_myna_benchmark_asgi_exceptions.jsonl"
messenger_docker_log_host="$run_artifact_dir/${run_stamp}_messenger_container.log"
outbox_docker_log_host="$run_artifact_dir/${run_stamp}_messenger_outbox_container.log"
outbox_status_host="$run_artifact_dir/${run_stamp}_realtime_outbox_status.json"
runtime_config_host="$run_artifact_dir/${run_stamp}_service_runtime_config.json"
readme_report_host="$resolved_report_dir/${run_stamp}_accurate_timing_README.md"

docker_env_args=()
for item in "${messenger_env_args[@]}"; do
  [[ "$item" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || die "Invalid Docker env assignment: $item"
  docker_env_args+=("-e" "$item")
done
outbox_common_docker_env_args=()
for item in "${messenger_env_args[@]}"; do
  [[ "$item" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || die "Invalid Docker env assignment: $item"
  outbox_common_docker_env_args+=("-e" "$item")
done
outbox_override_docker_env_args=()
for item in "${outbox_env_args[@]}"; do
  [[ "$item" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || die "Invalid Docker env assignment: $item"
  outbox_override_docker_env_args+=("-e" "$item")
done
runner_docker_env_args=()
for item in "${runner_env_args[@]}"; do
  [[ "$item" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || die "Invalid Docker env assignment: $item"
  runner_docker_env_args+=("-e" "$item")
done

capture_realtime_outbox_status() {
  local output_path="$1"
  local stage="$2"
  local since="$3"

  docker exec "$messenger_container" python manage.py shell -v 0 -c "
import json
from django.db.models import Count
from django.utils.dateparse import parse_datetime
from apps.realtime.models import RealtimeOutboxEvent

since = parse_datetime('$since') if '$since' else None
queryset = RealtimeOutboxEvent.objects.all()
if since is not None:
    queryset = queryset.filter(created_at__gte=since)
counts = {status: 0 for status, _label in RealtimeOutboxEvent.Status.choices}
counts.update({
    item['status']: item['count']
    for item in queryset.values('status').annotate(count=Count('id'))
})
print(json.dumps({
    'stage': '$stage',
    'since': '$since',
    'counts': counts,
    'total': sum(counts.values()),
}, sort_keys=True))
" > "$output_path"
}

outbox_status_value() {
  local path="$1"
  local expr="$2"
  python3 -c "
import json, sys
data = None
for raw in reversed(open(sys.argv[1], encoding='utf-8-sig').read().splitlines()):
    line = raw.strip()
    if not line.startswith('{'):
        continue
    try:
        data = json.loads(line)
        break
    except json.JSONDecodeError:
        continue
if data is None:
    raise SystemExit('No valid JSON object found in outbox status output')
print($expr)
" "$path"
}

wait_realtime_outbox_drain() {
  local since="$1"
  local timeout_seconds="$2"
  local poll_seconds="$3"
  local deadline=$((SECONDS + timeout_seconds))

  if [[ "$outbox_worker_enabled" != "true" ]]; then
    warn "Outbox worker is disabled; realtime outbox drain was not validated."
    printf '{"stage":"disabled","counts":{},"total":0}\n' > "$outbox_status_host"
    return 0
  fi

  info "Waiting for realtime outbox drain"
  while true; do
    if capture_realtime_outbox_status "$outbox_status_host" "after_benchmark_before_cleanup" "$since"; then
      local active_count
      local dead_count
      local total_count
      if active_count="$(outbox_status_value "$outbox_status_host" "sum(data['counts'].get(key, 0) for key in ('pending', 'processing', 'failed'))")" \
        && dead_count="$(outbox_status_value "$outbox_status_host" "data['counts'].get('dead', 0)")" \
        && total_count="$(outbox_status_value "$outbox_status_host" "data.get('total', 0)")"; then

        if [[ "$active_count" == "0" && "$dead_count" == "0" && "$total_count" != "0" ]]; then
          pass "Realtime outbox drained: $total_count event(s) observed since $since"
          return 0
        fi

        if [[ "$dead_count" != "0" ]]; then
          warn "Realtime outbox contains dead-letter event(s): $dead_count"
          return 1
        fi
      else
        warn "Could not parse realtime outbox status."
      fi
    else
      warn "Could not capture realtime outbox status."
    fi

    if (( SECONDS >= deadline )); then
      warn "Realtime outbox did not drain within ${timeout_seconds}s. See: $outbox_status_host"
      return 1
    fi

    sleep "$poll_seconds"
  done
}

info "Starting accurate-timing Docker-network benchmark"
ensure_network "$network_name"
container_running "$mysql_container" || die "MySQL benchmark container is not running: $mysql_container. Start it before running this accurate benchmark."
wait_mysql_ready "$mysql_container" "$root_password"
repair_benchmark_mysql_grants "$mysql_container" "$root_password" "$benchmark_user" "$benchmark_password"

if ! container_running "$redis_container"; then
  remove_container_if_exists "$redis_container"
  docker run -d --name "$redis_container" --network "$network_name" -p 6379:6379 redis:7-alpine >/dev/null
fi

for container in "$identity_container" "$messenger_container" "$outbox_container" "$runner_container" "$precheck_container"; do
  remove_container_if_exists "$container"
done

info "Building Identity image"
docker build -t "$identity_image" ./identity_service
info "Building Messenger image"
docker build -t "$messenger_image" ./messenger

info "Starting Identity"
docker run -d --name "$identity_container" --network "$network_name" --env-file "$identity_env_file" -p 5000:5000 "$identity_image" >/dev/null

info "Starting Messenger with benchmark-only Gunicorn access log"
docker run -d --name "$messenger_container" --network "$network_name" --env-file "$messenger_env_file" \
  "${docker_env_args[@]}" \
  -e GUNICORN_ACCESS_LOG=0 \
  -e "GUNICORN_ACCESS_LOG_FILE=$gunicorn_log_container" \
  -e "GUNICORN_ACCESS_LOG_FORMAT=$gunicorn_access_log_format" \
  -e MYNA_BENCHMARK_ASGI_ACCESS_LOG=1 \
  -e "MYNA_BENCHMARK_ASGI_ACCESS_LOG_FILE=$gunicorn_log_container" \
  -e "MYNA_BENCHMARK_ASGI_EXCEPTION_LOG_FILE=$exception_log_container" \
  -p 8000:8000 "$messenger_image" >/dev/null

wait_http_ok Identity http://127.0.0.1:5000/api/v1/health/
wait_http_ok Messenger http://127.0.0.1:8000/api/v1/health/

if [[ "$outbox_worker_enabled" == "true" ]]; then
  info "Starting Messenger realtime outbox worker"
  docker run -d --name "$outbox_container" --network "$network_name" --env-file "$messenger_env_file" \
    "${outbox_common_docker_env_args[@]}" \
    -e MESSENGER_PROCESS_ROLE=outbox \
    -e MESSENGER_HTTP_SERVER_MODE=wsgi \
    -e DB_CONN_MAX_AGE=0\
    "${outbox_override_docker_env_args[@]}" \
    "$messenger_image" >/dev/null
  sleep 2
  container_running "$outbox_container" || {
    docker logs "$outbox_container" --tail 100 || true
    die "Messenger realtime outbox worker did not stay running."
  }
fi

python3 - "$runtime_config_host" "$identity_container" "$messenger_container" "$outbox_container" "$outbox_worker_enabled" <<'PY'
import json
import subprocess
import sys

out, identity, messenger, outbox, outbox_enabled = sys.argv[1:6]
keys = [
    "WEB_CONCURRENCY",
    "ASGI_THREADS",
    "GUNICORN_THREADS",
    "GUNICORN_BACKLOG",
    "GUNICORN_TIMEOUT",
    "GUNICORN_GRACEFUL_TIMEOUT",
    "GUNICORN_KEEP_ALIVE",
    "GUNICORN_MAX_REQUESTS",
    "GUNICORN_MAX_REQUESTS_JITTER",
    "MESSENGER_PROCESS_ROLE",
    "MESSENGER_HTTP_SERVER_MODE",
    "DB_CONN_MAX_AGE",
    "DB_CONN_HEALTH_CHECKS",
    "REALTIME_OUTBOX_BATCH_SIZE",
    "REALTIME_OUTBOX_POLL_INTERVAL_SECONDS",
    "REALTIME_OUTBOX_MAX_ATTEMPTS",
    "REALTIME_OUTBOX_STALE_CLAIM_SECONDS",
    "REALTIME_OUTBOX_WORKER_ID",
]

def env_for(container):
    data = {}
    for key in keys:
        proc = subprocess.run(["docker", "exec", container, "printenv", key], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if proc.returncode == 0:
            data[key] = proc.stdout.strip()
    return data

services = {
    "identity": {"container": identity, "env": env_for(identity)},
    "messenger": {"container": messenger, "env": env_for(messenger)},
}
if outbox_enabled == "true":
    services["messenger_outbox"] = {"container": outbox, "env": env_for(outbox)}

json.dump(services, open(out, "w", encoding="utf-8"), indent=2)
PY

info "Building clean benchmark runner image"
docker build -t "$runner_image" -f ./messenger/Dockerfile.benchmark-runner ./messenger

benchmark_path="$(abs_path benchmark)"
api_tests_path="$(abs_path messenger/api_tests)"
env_path="$(abs_path "$runner_env_file")"
runner_report_dir="/reports/myna_api_test_reports/.${run_stamp}_accurate_timing_artifacts"
host_user_args=(--user "$(id -u):$(id -g)" -e PYTHONDONTWRITEBYTECODE=1)

docker run --rm --name "$precheck_container" --network "$network_name" --env-file "$env_path" \
  "${host_user_args[@]}" \
  -v "${benchmark_path}:/reports" "$runner_image" \
  -c "import urllib.request; print(urllib.request.urlopen('http://identity-service-local:5000/api/v1/health/', timeout=10).read().decode()); print(urllib.request.urlopen('http://messenger-service-local:8000/api/v1/health/', timeout=10).read().decode())"

printf 'timestamp,container,cpu_percent,mem_usage,mem_percent,net_io,block_io,pids\n' > "$host_stats_csv"
(
  while true; do
    timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    containers_to_sample=()
    for container in "$messenger_container" "$outbox_container" "$identity_container" "$mysql_container" "$redis_container"; do
      container_running "$container" || continue
      containers_to_sample+=("$container")
    done
    if ((${#containers_to_sample[@]})); then
      while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      python3 - "$timestamp" "$line" >> "$host_stats_csv" <<'PY'
import csv, sys
timestamp, line = sys.argv[1], sys.argv[2]
parts = [p.strip() for p in line.split(",", 6)]
if len(parts) == 7:
    parts[1] = parts[1].rstrip("%")
    parts[3] = parts[3].rstrip("%")
    csv.writer(sys.stdout).writerow([timestamp, parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]])
PY
      done < <(docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}' "${containers_to_sample[@]}" || true)
    fi
    sleep "$(python3 - "$docker_stats_interval_ms" <<'PY'
import sys
print(max(int(sys.argv[1]), 100) / 1000)
PY
)"
  done
) &
stats_pid=$!

outbox_observed_since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
benchmark_succeeded=false
benchmark_error=""
set +e
docker run --rm --name "$runner_container" --network "$network_name" --env-file "$env_path" \
  "${host_user_args[@]}" \
  "${runner_docker_env_args[@]}" \
  -e MYNA_CLEANUP_MESSENGER_DJANGO=false \
  -e MYNA_MESSENGER_DOCKER_CONTAINER= \
  -e MYNA_WRITE_LEGACY_MARKDOWN=false \
  -e "MYNA_REPORT_DIR=$runner_report_dir" \
  -v "${benchmark_path}:/reports" \
  -v "${api_tests_path}:/app/api_tests:ro" \
  "$runner_image" "$benchmark_script"
benchmark_exit=$?
set -e
kill "$stats_pid" >/dev/null 2>&1 || true
wait "$stats_pid" 2>/dev/null || true
if [[ "$benchmark_exit" -eq 0 ]]; then
  benchmark_succeeded=true
else
  benchmark_error="Docker-network benchmark failed with exit code $benchmark_exit"
  warn "$benchmark_error"
fi

outbox_drain_succeeded=true
if ! wait_realtime_outbox_drain "$outbox_observed_since" "$outbox_drain_timeout_seconds" "$outbox_drain_poll_seconds"; then
  outbox_drain_succeeded=false
  benchmark_succeeded=false
  benchmark_error="${benchmark_error:+$benchmark_error; }Realtime outbox drain validation failed"
fi

if [[ "$outbox_worker_enabled" == "true" ]]; then
  docker stop --time 10 "$outbox_container" >/dev/null 2>&1 || warn "Could not stop Messenger outbox worker before cleanup."
fi

docker cp "${messenger_container}:$gunicorn_log_container" "$gunicorn_log_host" >/dev/null 2>&1 || {
  warn "Could not copy Gunicorn access log from Messenger container."
  : > "$gunicorn_log_host"
}
docker cp "${messenger_container}:$exception_log_container" "$exception_log_host" >/dev/null 2>&1 || {
  warn "Could not copy benchmark ASGI exception log from Messenger container."
  : > "$exception_log_host"
}
docker logs "$messenger_container" > "$messenger_docker_log_host" 2>&1 || {
  warn "Could not capture Messenger Docker logs."
  : > "$messenger_docker_log_host"
}
if [[ "$outbox_worker_enabled" == "true" ]]; then
  docker logs "$outbox_container" > "$outbox_docker_log_host" 2>&1 || {
    warn "Could not capture Messenger outbox worker Docker logs."
    : > "$outbox_docker_log_host"
  }
else
  : > "$outbox_docker_log_host"
fi

cleanup_status_path=""
latest_before="$(latest_benchmark_json "$run_artifact_dir")"
if [[ -n "$latest_before" ]]; then
  cleanup_status_path="$run_artifact_dir/$(basename "$latest_before" .json)_host_side_messenger_cleanup_status.json"
fi
if [[ -n "$cleanup_status_path" ]]; then
  "$PWD/scripts/cleanup-docker-mysql-benchmark-messenger.sh" --root "$PWD" --status-output-path "$cleanup_status_path" --benchmark-mysql-root-password "$root_password" --benchmark-mysql-password "$benchmark_password" || warn "Host-side Messenger cleanup failed"
  "$PWD/scripts/patch-latest-benchmark-report-with-cleanup.sh" --root "$PWD" --cleanup-status-path "$cleanup_status_path" --json-report "$latest_before" || warn "Report cleanup patch failed"
fi

latest_json="$(latest_benchmark_json "$run_artifact_dir")"
[[ -n "$latest_json" ]] || die "No benchmark JSON report found in $run_artifact_dir"
request_gap_md=""

python3 - "$latest_json" "$outbox_status_host" "$outbox_worker_enabled" "$outbox_drain_succeeded" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
worker_enabled = sys.argv[3] == "true"
drain_succeeded = sys.argv[4] == "true"

report = json.loads(report_path.read_text(encoding="utf-8-sig"))
status = None
status_parse_error = None
if status_path.exists():
    for line in reversed(status_path.read_text(encoding="utf-8-sig").splitlines()):
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            status = json.loads(text)
            status_parse_error = None
            break
        except json.JSONDecodeError as exc:
            status_parse_error = f"{exc.__class__.__name__}: {exc}"
    if status is None and status_parse_error is None:
        status_parse_error = "No JSON object line found in outbox status output"

report["realtime_outbox_drain_validation"] = {
    "worker_enabled": worker_enabled,
    "succeeded": drain_succeeded,
    "status_path": str(status_path),
    "status": status,
    "status_parse_error": status_parse_error,
}
report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
PY

set +e
python3 ./scripts/analyze-benchmark-request-gaps.py \
  --json-report "$latest_json" \
  --gunicorn-log "$gunicorn_log_host" \
  --server-exception-log "$exception_log_host" \
  --docker-stats-csv "$host_stats_csv" \
  --runtime-config-json "$runtime_config_host" \
  --output-json "$latest_json" \
  --skip-md
analyzer_exit=$?
set -e
[[ "$analyzer_exit" -eq 0 ]] || warn "Request-gap analyzer completed with warnings or matching failure. Exit code: $analyzer_exit"

info "Accurate timing report"
printf '  Primary JSON used by README:   %s\n' "$latest_json"
if [[ "$write_readme" != true || "$cleanup_artifacts" != true ]]; then
  printf '  Raw artifact directory:        %s\n' "$run_artifact_dir"
fi

if [[ -n "$run_metadata_output_path" ]]; then
  mkdir -p "$(dirname "$run_metadata_output_path")"
  python3 - "$run_label" "$benchmark_script" "$benchmark_succeeded" "$benchmark_error" "$analyzer_exit" "$latest_json" "$request_gap_md" "$gunicorn_log_host" "$host_stats_csv" "$cleanup_status_path" "$run_metadata_output_path" "$exception_log_host" "$messenger_docker_log_host" "$outbox_docker_log_host" "$outbox_status_host" "$outbox_worker_enabled" "$outbox_drain_succeeded" "$readme_report_host" "${messenger_env_args[@]}" --outbox "${outbox_env_args[@]}" --runner "${runner_env_args[@]}" <<'PY'
import datetime, json, sys
outbox_sep = sys.argv.index("--outbox")
runner_sep = sys.argv.index("--runner")
messenger_env = dict(item.split("=", 1) for item in sys.argv[19:outbox_sep] if "=" in item)
outbox_env = dict(item.split("=", 1) for item in sys.argv[outbox_sep+1:runner_sep] if "=" in item)
runner_env = dict(item.split("=", 1) for item in sys.argv[runner_sep+1:] if "=" in item)
metadata = {
    "run_label": sys.argv[1],
    "benchmark_script": sys.argv[2],
    "benchmark_succeeded": sys.argv[3] == "true",
    "benchmark_error": sys.argv[4] or None,
    "analyzer_exit_code": int(sys.argv[5]),
    "messenger_env": messenger_env,
    "runner_env": runner_env,
    "json_report_path": sys.argv[6],
    "gap_report_path": sys.argv[7] or None,
    "gunicorn_access_log_path": sys.argv[8],
    "host_docker_stats_csv_path": sys.argv[9],
    "cleanup_status_path": sys.argv[10],
    "server_exception_log_path": sys.argv[12],
    "messenger_container_log_path": sys.argv[13],
    "outbox_container_log_path": sys.argv[14],
    "realtime_outbox_status_path": sys.argv[15],
    "outbox_worker_enabled": sys.argv[16] == "true",
    "outbox_drain_succeeded": sys.argv[17] == "true",
    "readme_report_path": sys.argv[18] or None,
    "outbox_env": outbox_env,
    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
json.dump(metadata, open(sys.argv[11], "w", encoding="utf-8"), indent=2)
PY
  printf '  Run metadata:                 %s\n' "$run_metadata_output_path"
fi

if [[ "$write_readme" == true ]]; then
  readme_args=(accurate --json-report "$latest_json" --output-md "$readme_report_host")
  if [[ "$cleanup_artifacts" == true ]]; then
    readme_args+=(--omit-source-paths)
  fi
  if [[ -n "$run_metadata_output_path" && -f "$run_metadata_output_path" ]]; then
    readme_args+=(--run-metadata-json "$run_metadata_output_path")
  fi
  python3 ./scripts/build-benchmark-readme-report.py "${readme_args[@]}"
  printf '  README report:                %s\n' "$readme_report_host"
  if [[ "$cleanup_artifacts" == true ]]; then
    remove_report_artifact_dir "$resolved_report_dir" "$run_artifact_dir"
    printf '  Raw artifacts:                deleted after README generation\n'
  fi
fi

[[ "$benchmark_succeeded" == true ]] || die "Benchmark workflow failed before cleanup/analyze completed: $benchmark_error"
[[ "$analyzer_exit" -eq 0 ]] || die "Request-gap analysis completed but reported matching warnings. See files above."
