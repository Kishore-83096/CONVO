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
messenger_container_1="messenger-service-local-1"
messenger_container_2="messenger-service-local-2"
messenger_lb_container="messenger-load-balancer-local"
# Keep messenger_container pointing at instance 1 for DB/outbox inspection helpers.
messenger_container="$messenger_container_1"
outbox_container="messenger-outbox-local"
identity_image="identity-service-local:dev"
messenger_image="messenger-service-local:dev"
runner_image="messenger-benchmark-runner-local:dev"
messenger_lb_image="${MYNA_MESSENGER_LB_IMAGE:-nginx:alpine}"
messenger_lb_url="http://${messenger_lb_container}:8000"
messenger_lb_host_port="${MYNA_MESSENGER_LB_HOST_PORT:-18000}"
runner_container="myna-benchmark-runner"
precheck_container="myna-benchmark-runner-precheck"
gunicorn_log_container="/tmp/myna_benchmark_gunicorn_access.log"
gthread_queue_log_container="/tmp/myna_gthread_queue.log"
exception_log_container="/tmp/myna_benchmark_asgi_exceptions.jsonl"
gunicorn_access_log_format='%(t)s pid=%(p)s status=%(s)s duration_us=%(D)s method="%(m)s" path="%(U)s" run="%({x-myna-benchmark-run-id}i)s" req="%({x-myna-benchmark-request-id}i)s" phase="%({x-myna-benchmark-phase}i)s" concurrency="%({x-myna-benchmark-concurrency}i)s"'

resolved_report_dir="$(abs_path "$report_dir")"
mkdir -p "$resolved_report_dir"
run_stamp="$(date +%H-%M-%S_%Y-%m-%d)"
run_artifact_dir="$resolved_report_dir/.${run_stamp}_accurate_timing_artifacts"
mkdir -p "$run_artifact_dir"
host_stats_csv="$run_artifact_dir/${run_stamp}_host_docker_stats.csv"
gunicorn_log_host="$run_artifact_dir/${run_stamp}_myna_benchmark_gunicorn_access.log"
gunicorn_log_host_1="$run_artifact_dir/${run_stamp}_myna_benchmark_gunicorn_access_instance_1.log"
gunicorn_log_host_2="$run_artifact_dir/${run_stamp}_myna_benchmark_gunicorn_access_instance_2.log"
gthread_queue_log_host="$run_artifact_dir/${run_stamp}_myna_gthread_queue.log"
gthread_queue_log_host_1="$run_artifact_dir/${run_stamp}_myna_gthread_queue_instance_1.log"
gthread_queue_log_host_2="$run_artifact_dir/${run_stamp}_myna_gthread_queue_instance_2.log"
exception_log_host="$run_artifact_dir/${run_stamp}_myna_benchmark_asgi_exceptions.jsonl"
exception_log_host_1="$run_artifact_dir/${run_stamp}_myna_benchmark_asgi_exceptions_instance_1.jsonl"
exception_log_host_2="$run_artifact_dir/${run_stamp}_myna_benchmark_asgi_exceptions_instance_2.jsonl"
messenger_docker_log_host="$run_artifact_dir/${run_stamp}_messenger_container.log"
messenger_docker_log_host_1="$run_artifact_dir/${run_stamp}_messenger_instance_1_container.log"
messenger_docker_log_host_2="$run_artifact_dir/${run_stamp}_messenger_instance_2_container.log"
messenger_lb_docker_log_host="$run_artifact_dir/${run_stamp}_messenger_load_balancer_container.log"
messenger_lb_config_host="$run_artifact_dir/${run_stamp}_messenger_load_balancer_nginx.conf"
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

info "Starting two-Messenger load-balanced accurate-timing Docker-network benchmark"
ensure_network "$network_name"
container_running "$mysql_container" || die "MySQL benchmark container is not running: $mysql_container. Start it before running this accurate benchmark."
wait_mysql_ready "$mysql_container" "$root_password"
repair_benchmark_mysql_grants "$mysql_container" "$root_password" "$benchmark_user" "$benchmark_password"

if ! container_running "$redis_container"; then
  remove_container_if_exists "$redis_container"
  docker run -d --name "$redis_container" --network "$network_name" -p 6379:6379 redis:7-alpine >/dev/null
fi

for container in "$identity_container" "$messenger_container_1" "$messenger_container_2" "$messenger_lb_container" "$outbox_container" "$runner_container" "$precheck_container"; do
  remove_container_if_exists "$container"
done

info "Building Identity image"
docker build -t "$identity_image" ./identity_service
info "Building Messenger image"
docker build -t "$messenger_image" ./messenger

info "Starting Identity"
docker run -d --name "$identity_container" --network "$network_name" --env-file "$identity_env_file" -p 5000:5000 "$identity_image" >/dev/null

start_messenger_instance() {
  local container_name="$1"
  info "Starting ${container_name} with benchmark queue instrumentation"
  docker run -d --name "$container_name" --network "$network_name" --env-file "$messenger_env_file" \
    "${docker_env_args[@]}" \
    -e GUNICORN_ACCESS_LOG=0 \
    -e "GUNICORN_ACCESS_LOG_FILE=$gunicorn_log_container" \
    -e "GUNICORN_ACCESS_LOG_FORMAT=$gunicorn_access_log_format" \
    -e MYNA_BENCHMARK_ASGI_ACCESS_LOG=1 \
    -e "MYNA_BENCHMARK_ASGI_ACCESS_LOG_FILE=$gunicorn_log_container" \
    -e "MYNA_BENCHMARK_ASGI_EXCEPTION_LOG_FILE=$exception_log_container" \
    "$messenger_image" >/dev/null
}

start_messenger_instance "$messenger_container_1"
start_messenger_instance "$messenger_container_2"

cat > "$messenger_lb_config_host" <<EOF
worker_processes 1;

events {
    worker_connections 4096;
}

http {
    upstream messenger_backend {
        server ${messenger_container_1}:8000 max_fails=3 fail_timeout=2s;
        server ${messenger_container_2}:8000 max_fails=3 fail_timeout=2s;

        keepalive 64;
        keepalive_timeout 4s;
    }

    server {
        listen 8000;
        access_log off;

        location / {
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            # Preserve the same Host value used by the previous direct-container test.
            proxy_set_header Host messenger-service-local;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_connect_timeout 5s;
            proxy_read_timeout 60s;
            proxy_pass http://messenger_backend;
        }
    }
}
EOF

info "Starting local Nginx load balancer for two Messenger instances"
docker run -d --name "$messenger_lb_container" --network "$network_name" \
  -p "127.0.0.1:${messenger_lb_host_port}:8000" \
  -v "${messenger_lb_config_host}:/etc/nginx/nginx.conf:ro" \
  "$messenger_lb_image" >/dev/null

wait_http_ok Identity http://127.0.0.1:5000/api/v1/health/
wait_http_ok "Messenger load balancer" "http://127.0.0.1:${messenger_lb_host_port}/api/v1/health/"

if [[ "$outbox_worker_enabled" == "true" ]]; then
  info "Starting Messenger realtime outbox worker"
  docker run -d --name "$outbox_container" --network "$network_name" --env-file "$messenger_env_file" \
    "${outbox_common_docker_env_args[@]}" \
    -e MESSENGER_PROCESS_ROLE=outbox \
    -e MESSENGER_HTTP_SERVER_MODE=wsgi \
    -e DB_CONN_MAX_AGE=60\
    "${outbox_override_docker_env_args[@]}" \
    "$messenger_image" >/dev/null
  sleep 2
  container_running "$outbox_container" || {
    docker logs "$outbox_container" --tail 100 || true
    die "Messenger realtime outbox worker did not stay running."
  }
fi

python3 - "$runtime_config_host" "$identity_container" "$messenger_container_1" "$messenger_container_2" "$messenger_lb_container" "$outbox_container" "$outbox_worker_enabled" <<'PY'
import json
import subprocess
import sys

out, identity, messenger_1, messenger_2, messenger_lb, outbox, outbox_enabled = sys.argv[1:8]
keys = [
    "WEB_CONCURRENCY",
    "ASGI_THREADS",
    "GUNICORN_THREADS",
    "GUNICORN_WORKER_CLASS",
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
    "MYNA_GTHREAD_QUEUE_WRITER_BATCH_SIZE",
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
    # Preserve the standard "messenger" report key using instance 1 so the
    # existing README builder keeps reporting workers/threads/config.
    "messenger": {"container": messenger_1, "env": env_for(messenger_1)},
    "messenger_instance_2": {"container": messenger_2, "env": env_for(messenger_2)},
    "messenger_load_balancer": {
        "container": messenger_lb,
        "env": {},
        "upstreams": [messenger_1, messenger_2],
        "method": "nginx default round-robin",
    },
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
  -e "MYNA_LOCAL_MESSENGER_BASE_URL=$messenger_lb_url" \
  -v "${benchmark_path}:/reports" "$runner_image" \
  -c "import urllib.request; print(urllib.request.urlopen('http://identity-service-local:5000/api/v1/health/', timeout=10).read().decode()); print(urllib.request.urlopen('${messenger_lb_url}/api/v1/health/', timeout=10).read().decode())"

printf 'timestamp,container,cpu_percent,mem_usage,mem_percent,net_io,block_io,pids\n' > "$host_stats_csv"
(
  while true; do
    timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    containers_to_sample=()
    for container in "$messenger_container_1" "$messenger_container_2" "$messenger_lb_container" "$outbox_container" "$identity_container" "$mysql_container" "$redis_container"; do
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
  -e "MYNA_LOCAL_MESSENGER_BASE_URL=$messenger_lb_url" \
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

# The queue collector writes on one background thread per Gunicorn worker.
# This delay is outside the measured benchmark and lets pending in-memory
# queue records drain before the container log file is copied.
queue_collector_drain_seconds="${MYNA_GTHREAD_QUEUE_COLLECTOR_DRAIN_SECONDS:-1}"
sleep "$queue_collector_drain_seconds"

copy_container_log_file() {
  local container_name="$1"
  local container_path="$2"
  local host_path="$3"
  local description="$4"
  docker cp "${container_name}:${container_path}" "$host_path" >/dev/null 2>&1 || {
    warn "Could not copy ${description} from ${container_name}."
    : > "$host_path"
  }
}

copy_container_log_file "$messenger_container_1" "$gunicorn_log_container" "$gunicorn_log_host_1" "Gunicorn access log"
copy_container_log_file "$messenger_container_2" "$gunicorn_log_container" "$gunicorn_log_host_2" "Gunicorn access log"
cat "$gunicorn_log_host_1" "$gunicorn_log_host_2" > "$gunicorn_log_host"

copy_container_log_file "$messenger_container_1" "$gthread_queue_log_container" "$gthread_queue_log_host_1" "Gunicorn gthread queue log"
copy_container_log_file "$messenger_container_2" "$gthread_queue_log_container" "$gthread_queue_log_host_2" "Gunicorn gthread queue log"

# Docker PID namespaces can reuse the same numeric Gunicorn PIDs. Prefix the
# worker identity in each queue log before merging so the existing analyzer
# counts all 12 workers instead of accidentally collapsing same-numbered PIDs.
python3 - "$gthread_queue_log_host_1" "$gthread_queue_log_host_2" "$gthread_queue_log_host" <<'PY'
import sys
from pathlib import Path

sources = [
    ("messenger-1", Path(sys.argv[1])),
    ("messenger-2", Path(sys.argv[2])),
]
output = Path(sys.argv[3])

lines = []
pid_fields = ("worker_pid=", "enqueue_worker_pid=", "handle_worker_pid=")
for instance, source in sources:
    if not source.exists():
        continue
    for raw in source.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        tokens = []
        for token in raw.split():
            for prefix in pid_fields:
                if token.startswith(prefix):
                    token = f"{prefix}{instance}:{token[len(prefix):]}"
                    break
            tokens.append(token)
        lines.append(" ".join(tokens))

output.write_text(
    "".join(f"{line}\n" for line in lines),
    encoding="utf-8",
)
PY

copy_container_log_file "$messenger_container_1" "$exception_log_container" "$exception_log_host_1" "benchmark ASGI exception log"
copy_container_log_file "$messenger_container_2" "$exception_log_container" "$exception_log_host_2" "benchmark ASGI exception log"
cat "$exception_log_host_1" "$exception_log_host_2" > "$exception_log_host"

docker logs "$messenger_container_1" > "$messenger_docker_log_host_1" 2>&1 || {
  warn "Could not capture Messenger instance 1 Docker logs."
  : > "$messenger_docker_log_host_1"
}
docker logs "$messenger_container_2" > "$messenger_docker_log_host_2" 2>&1 || {
  warn "Could not capture Messenger instance 2 Docker logs."
  : > "$messenger_docker_log_host_2"
}
{
  printf '===== %s =====\n' "$messenger_container_1"
  cat "$messenger_docker_log_host_1"
  printf '\n===== %s =====\n' "$messenger_container_2"
  cat "$messenger_docker_log_host_2"
} > "$messenger_docker_log_host"

docker logs "$messenger_lb_container" > "$messenger_lb_docker_log_host" 2>&1 || {
  warn "Could not capture Messenger load balancer Docker logs."
  : > "$messenger_lb_docker_log_host"
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

info "Aggregating Gunicorn gthread queue and worker distribution metrics"
python3 - "$latest_json" "$gthread_queue_log_host" <<'PY'
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

report_path = Path(sys.argv[1])
queue_log_path = Path(sys.argv[2])
report = json.loads(report_path.read_text(encoding="utf-8-sig"))
run_id = str(report.get("run_id") or "").strip()
levels = list((report.get("benchmark") or {}).get("per_level") or [])


def parse_line(raw_line):
    fields = {}
    for token in raw_line.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * weight)


def rounded(value):
    return round(float(value), 2) if value is not None else None


def summarize(values):
    clean = [float(value) for value in values]
    if not clean:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "avg": None,
            "p50": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "p99": None,
        }
    p50 = percentile(clean, 0.50)
    return {
        "count": len(clean),
        "min": rounded(min(clean)),
        "max": rounded(max(clean)),
        "avg": rounded(statistics.mean(clean)),
        "p50": rounded(p50),
        "median": rounded(p50),
        "p75": rounded(percentile(clean, 0.75)),
        "p90": rounded(percentile(clean, 0.90)),
        "p95": rounded(percentile(clean, 0.95)),
        "p99": rounded(percentile(clean, 0.99)),
    }


def pearson(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    numerator = sum(left * right for left, right in zip(dx, dy))
    denominator = math.sqrt(
        sum(value * value for value in dx)
        * sum(value * value for value in dy)
    )
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


raw_lines = []
read_error = None
try:
    raw_lines = queue_log_path.read_text(encoding="utf-8-sig").splitlines()
except OSError as exc:
    read_error = f"{exc.__class__.__name__}: {exc}"

parsed_rows = [parse_line(line) for line in raw_lines if line.strip()]
run_rows = [row for row in parsed_rows if row.get("run") == run_id]

analysis = {
    "available": False,
    "collector": "messenger_config.benchmark_gthread_worker.BenchmarkThreadWorker",
    "collector_io_mode": "per_worker_simplequeue_background_batch_writer",
    "run_id": run_id,
    "queue_log_present": queue_log_path.is_file(),
    "queue_log_nonempty": bool(raw_lines),
    "queue_log_read_error": read_error,
    "raw_log_line_count": len(raw_lines),
    "matching_run_line_count": len(run_rows),
    "per_level": [],
    "warnings": [],
}

if not run_id:
    analysis["warnings"].append("Primary JSON report has no run_id; queue records cannot be correlated.")

for level in levels:
    try:
        concurrency = int(level.get("concurrency"))
    except (TypeError, ValueError):
        continue

    expected_phase = f"send_concurrency_{concurrency}"
    level_rows = []
    for row in run_rows:
        try:
            row_concurrency = int(row.get("concurrency") or 0)
        except (TypeError, ValueError):
            continue
        if row_concurrency != concurrency or row.get("phase") != expected_phase:
            continue
        try:
            queue_wait_ms = int(row.get("queue_wait_us") or 0) / 1000.0
        except (TypeError, ValueError):
            continue
        enriched = dict(row)
        enriched["queue_wait_ms"] = queue_wait_ms
        level_rows.append(enriched)

    by_worker = defaultdict(list)
    by_thread = defaultdict(list)
    queue_by_request = {}

    for row in level_rows:
        worker_pid = str(row.get("worker_pid") or "missing")
        thread_ident = str(row.get("thread_ident") or "missing")
        thread_name = str(row.get("thread_name") or "missing")
        queue_wait_ms = float(row["queue_wait_ms"])
        by_worker[worker_pid].append(queue_wait_ms)
        by_thread[(worker_pid, thread_ident, thread_name)].append(queue_wait_ms)
        request_id = str(row.get("req") or "").strip()
        if request_id:
            queue_by_request[request_id] = queue_wait_ms

    worker_distribution = []
    for worker_pid, values in sorted(
        by_worker.items(),
        key=lambda item: (-len(item[1]), item[0]),
    ):
        worker_distribution.append({
            "worker_pid": worker_pid,
            "request_count": len(values),
            "request_share_pct": round((len(values) / len(level_rows)) * 100, 2)
            if level_rows else None,
            "queue_wait_ms": summarize(values),
        })

    thread_distribution = []
    for (worker_pid, thread_ident, thread_name), values in sorted(
        by_thread.items(),
        key=lambda item: (item[0][0], -len(item[1]), item[0][1]),
    ):
        thread_distribution.append({
            "worker_pid": worker_pid,
            "thread_ident": thread_ident,
            "thread_name": thread_name,
            "request_count": len(values),
            "request_share_pct": round((len(values) / len(level_rows)) * 100, 2)
            if level_rows else None,
            "queue_wait_ms": summarize(values),
        })

    worker_counts = [len(values) for values in by_worker.values()]
    thread_counts = [len(values) for values in by_thread.values()]
    distribution_summary = {
        "worker_count": len(worker_counts),
        "thread_count": len(thread_counts),
        "worker_requests_min": min(worker_counts) if worker_counts else None,
        "worker_requests_max": max(worker_counts) if worker_counts else None,
        "worker_request_spread": (
            max(worker_counts) - min(worker_counts)
            if worker_counts else None
        ),
        "worker_requests_mean": (
            round(statistics.mean(worker_counts), 2)
            if worker_counts else None
        ),
        "worker_requests_stdev": (
            round(statistics.pstdev(worker_counts), 2)
            if worker_counts else None
        ),
        "worker_request_cv_pct": (
            round(
                (
                    statistics.pstdev(worker_counts)
                    / statistics.mean(worker_counts)
                ) * 100,
                2,
            )
            if worker_counts and statistics.mean(worker_counts) != 0
            else None
        ),
        "worker_max_to_min_request_ratio": (
            round(max(worker_counts) / min(worker_counts), 4)
            if worker_counts and min(worker_counts) > 0
            else None
        ),
        "thread_requests_min": min(thread_counts) if thread_counts else None,
        "thread_requests_max": max(thread_counts) if thread_counts else None,
        "thread_request_spread": (
            max(thread_counts) - min(thread_counts)
            if thread_counts else None
        ),
        "thread_requests_mean": (
            round(statistics.mean(thread_counts), 2)
            if thread_counts else None
        ),
    }

    request_records = list(level.get("request_records") or [])
    httpx_wait_by_request = {}
    for record in request_records:
        request_id = str(record.get("benchmark_request_id") or "").strip()
        trace = record.get("httpx_trace_ms") or {}
        wait_ms = trace.get("wait_response_headers")
        if request_id and wait_ms is not None:
            try:
                httpx_wait_by_request[request_id] = float(wait_ms)
            except (TypeError, ValueError):
                pass

    matched_ids = sorted(set(queue_by_request) & set(httpx_wait_by_request))
    queue_values = [queue_by_request[request_id] for request_id in matched_ids]
    httpx_wait_values = [
        httpx_wait_by_request[request_id]
        for request_id in matched_ids
    ]
    header_wait_minus_queue = [
        httpx_wait_by_request[request_id] - queue_by_request[request_id]
        for request_id in matched_ids
    ]

    queue_summary = summarize(
        [row["queue_wait_ms"] for row in level_rows]
    )
    httpx_wait_summary = (
        (level.get("httpx_trace_ms") or {})
        .get("wait_response_headers")
        or {}
    )
    queue_avg = queue_summary.get("avg")
    httpx_wait_avg = httpx_wait_summary.get("avg")

    request_correlation = {
        "matched_request_count": len(matched_ids),
        "queue_request_count": len(queue_by_request),
        "httpx_wait_request_count": len(httpx_wait_by_request),
        "unmatched_queue_request_count": len(
            set(queue_by_request) - set(httpx_wait_by_request)
        ),
        "unmatched_httpx_request_count": len(
            set(httpx_wait_by_request) - set(queue_by_request)
        ),
        "pearson_queue_vs_httpx_wait_response_headers": pearson(
            queue_values,
            httpx_wait_values,
        ),
        "httpx_wait_response_headers_minus_queue_ms": summarize(
            header_wait_minus_queue
        ),
        "queue_share_of_httpx_wait_response_headers_avg_pct": (
            round((queue_avg / float(httpx_wait_avg)) * 100, 2)
            if queue_avg is not None
            and httpx_wait_avg not in (None, 0)
            else None
        ),
        "average_boundary_note": (
            "queue_share_of_httpx_wait_response_headers_avg_pct compares "
            "population averages. The Pearson value and delta summary are "
            "computed after joining individual requests by benchmark_request_id."
        ),
    }

    expected_requests = int(level.get("total_messages") or 0)
    level_warnings = []
    if len(level_rows) != expected_requests:
        level_warnings.append(
            f"Expected {expected_requests} measured queue samples but found "
            f"{len(level_rows)} for phase {expected_phase}."
        )
    if request_correlation["matched_request_count"] != expected_requests:
        level_warnings.append(
            f"Per-request queue/HTTPX join matched "
            f"{request_correlation['matched_request_count']} of "
            f"{expected_requests} measured requests."
        )

    analysis["per_level"].append({
        "concurrency": concurrency,
        "phase": expected_phase,
        "expected_request_count": expected_requests,
        "sample_count": len(level_rows),
        "queue_wait_ms": queue_summary,
        "distribution_summary": distribution_summary,
        "worker_distribution": worker_distribution,
        "thread_distribution": thread_distribution,
        "request_correlation": request_correlation,
        "warnings": level_warnings,
    })

analysis["available"] = any(
    int(item.get("sample_count") or 0) > 0
    for item in analysis["per_level"]
)
if not analysis["available"]:
    analysis["warnings"].append(
        "No measured send_concurrency_<N> gthread queue samples were found "
        "for the exact benchmark run_id."
    )

report["gunicorn_gthread_queue_analysis"] = analysis
report_path.write_text(
    json.dumps(report, indent=2, default=str),
    encoding="utf-8",
)
PY

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
