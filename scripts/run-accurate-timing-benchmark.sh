#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$repo_root"

runner_env=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runner-env)
      [[ $# -ge 2 ]] || { echo "--runner-env requires KEY=VALUE" >&2; exit 2; }
      [[ "$2" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || { echo "Invalid env assignment: $2" >&2; exit 2; }
      runner_env+=("$2")
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./benchmark/scripts/run-accurate-timing-benchmark.sh [--runner-env KEY=VALUE ...]

Examples:
  ./benchmark/scripts/run-accurate-timing-benchmark.sh
  ./benchmark/scripts/run-accurate-timing-benchmark.sh \
    --runner-env MYNA_DISTRIBUTED_PAIR_COUNT=100 \
    --runner-env MYNA_BENCHMARK_LEVELS=1,5,10,25,50,75,100
EOF
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -f .env ]] || { echo "Missing .env. Run ./scripts/migrate-env-to-root.sh first." >&2; exit 2; }
[[ -f compose.yml ]] || { echo "Missing compose.yml" >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo "Docker CLI is required" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "Docker daemon is not available" >&2; exit 2; }

wait_healthy() {
  local service="$1"
  local id status
  for _ in $(seq 1 60); do
    id="$(docker compose --env-file .env -f compose.yml ps -q "$service")"
    if [[ -n "$id" ]]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null || true)"
      [[ "$status" == "healthy" ]] && return 0
    fi
    sleep 2
  done
  docker compose --env-file .env -f compose.yml logs --tail 120 "$service" || true
  echo "$service did not become healthy" >&2
  return 1
}

restore_normal_services() {
  echo "==> Restoring normal .env runtime settings"
  docker compose --env-file .env -f compose.yml up -d --force-recreate identity messenger >/dev/null 2>&1 || true
}
benchmark_container_name="myna-accurate-timing-benchmark"

cleanup_benchmark_container() {
  docker rm -f "$benchmark_container_name" >/dev/null 2>&1 || true
}

restore_needed=true
trap 'cleanup_benchmark_container; if [[ "$restore_needed" == true ]]; then restore_normal_services; fi' EXIT

# Start the canonical local architecture first.
./scripts/start-backend.sh

# Benchmark setup/cleanup intentionally creates and deletes many users. Recreate
# Identity with benchmark-only high local limits, and Messenger with direct-send
# profiling enabled. These overrides are process environment for Compose only and
# are not written back to .env.
echo "==> Enabling benchmark-only Identity rate limits and Messenger profiling"
REGISTER_RATE_LIMIT='100000 per minute' \
LOGIN_RATE_LIMIT='100000 per minute' \
RESET_PASSWORD_RATE_LIMIT='100000 per minute' \
DELETE_ACCOUNT_RATE_LIMIT='100000 per minute' \
CONTACT_SEARCH_RATE_LIMIT='100000 per minute' \
CONTACT_ADD_RATE_LIMIT='100000 per minute' \
docker compose --env-file .env -f compose.yml up -d --force-recreate identity
MYNA_PROFILE_DIRECT_SEND=true \
docker compose --env-file .env -f compose.yml up -d --force-recreate messenger
wait_healthy identity
wait_healthy messenger

messenger_id="$(docker compose --env-file .env -f compose.yml ps -q messenger)"
[[ -n "$messenger_id" ]] || { echo "Messenger container is not running" >&2; exit 1; }

docker exec "$messenger_id" sh -c ': > /tmp/myna_benchmark_gunicorn_access.log; : > /tmp/myna_gthread_queue.log; : > /tmp/myna_benchmark_asgi_exceptions.jsonl' || true

report_dir="$repo_root/benchmark/reports"
mkdir -p "$report_dir"
stamp="$(date +%H-%M-%S_%Y-%m-%d)"
artifact_dir="$report_dir/.${stamp}_accurate_timing_artifacts"
container_report_stage="$artifact_dir/container-reports"
mkdir -p "$artifact_dir" "$container_report_stage"
runtime_env_file="$artifact_dir/runner.env"
gunicorn_log="$artifact_dir/${stamp}_gunicorn_access.log"
queue_log="$artifact_dir/${stamp}_gthread_queue.log"
exception_log="$artifact_dir/${stamp}_server_exceptions.jsonl"
runtime_config="$artifact_dir/${stamp}_runtime_config.json"
docker_stats_csv="$artifact_dir/${stamp}_docker_stats.csv"
: > "$docker_stats_csv"

python3 - "$repo_root/.env" "$runtime_env_file" "${runner_env[@]}" <<'PY'
from __future__ import annotations
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
overrides = sys.argv[3:]

values: dict[str, str] = {}
for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key.strip()] = value.strip()

fixed = {
    "DATABASE_URL": values["MESSENGER_DATABASE_URL"],
    "JWT_VERIFYING_KEY": values["JWT_SECRET_KEY"],
    "CONTACT_POLICY_SYNC_SECRET": values["MESSENGER_INTERNAL_SECRET"],
    "CLOUDINARY_FOLDER": values.get("MESSENGER_CLOUDINARY_FOLDER", "Mynav2/local/attachments"),
    "MESSENGER_PROCESS_ROLE": "http",
    "MYNA_SERVICE_URL_MODE": "docker",
    "MYNA_DOCKER_IDENTITY_BASE_URL": "http://identity:5000",
    "MYNA_DOCKER_MESSENGER_BASE_URL": "http://messenger:8000",
    "MYNA_IDENTITY_BASE_URL": "http://identity:5000",
    "MYNA_MESSENGER_BASE_URL": "http://messenger:8000",
    "MYNA_MESSENGER_DOCKER_CONTAINER": "",
    "MYNA_IDENTITY_DOCKER_CONTAINER": "",
    "MYNA_POSTGRES_DOCKER_CONTAINER": "",
    "MYNA_MESSENGER_PROJECT_ROOT": "/app",
    "MYNA_REPORT_DIR": "/tmp/myna-reports",
    "MYNA_WRITE_LEGACY_MARKDOWN": "false",
    "MYNA_DOCKER_STATS_ENABLED": "false",
    "MYNA_CLEANUP_MESSENGER_DJANGO": "true",
    "MYNA_CLEANUP_IDENTITY_USERS": "true",
    "MYNA_OUTBOX_DRAIN_ENABLED": "true",
}
values.update(fixed)
for item in overrides:
    key, value = item.split("=", 1)
    values[key] = value
out_path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
out_path.chmod(0o600)
PY

echo "==> Building the root benchmark runner image"
docker build -t myna-benchmark:local -f benchmark/Dockerfile .

runner_exit=0
echo "==> Running accurate-timing distributed-pairs benchmark inside Docker DNS network"
cleanup_benchmark_container
set +e
docker run \
  --name "$benchmark_container_name" \
  --network myna-local \
  --env-file "$runtime_env_file" \
  myna-benchmark:local \
  /benchmark/runner/myna_distributed_pairs_latency_benchmark_test.py
runner_exit=$?
set -e

echo "==> Copying benchmark reports out of the stopped runner container"
docker cp "$benchmark_container_name:/tmp/myna-reports/." "$container_report_stage/"
cleanup_benchmark_container

# The non-blocking queue collector writes through a background thread per Gunicorn
# worker. This short delay is outside measured traffic and lets queued log records flush.
sleep "${MYNA_GTHREAD_QUEUE_COLLECTOR_DRAIN_SECONDS:-1}"

docker cp "$messenger_id:/tmp/myna_benchmark_gunicorn_access.log" "$gunicorn_log" 2>/dev/null || : > "$gunicorn_log"
docker cp "$messenger_id:/tmp/myna_gthread_queue.log" "$queue_log" 2>/dev/null || : > "$queue_log"
docker cp "$messenger_id:/tmp/myna_benchmark_asgi_exceptions.jsonl" "$exception_log" 2>/dev/null || : > "$exception_log"

docker compose --env-file .env -f compose.yml exec -T messenger python manage.py shell -v 0 -c \
  'import json; from django.conf import settings; print(json.dumps(settings.MESSENGER_RUNTIME_CONFIGURATION, sort_keys=True))' \
  > "$runtime_config"

container_json="$(python3 - "$container_report_stage" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
candidates = []
for path in root.glob("*.json"):
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        continue
    if isinstance(obj.get("benchmark"), dict) and isinstance(obj.get("summary"), dict):
        candidates.append(path)
if not candidates:
    raise SystemExit(1)
print(max(candidates, key=lambda p: p.stat().st_mtime))
PY
)" || { echo "Benchmark did not produce a primary JSON report" >&2; exit 1; }

latest_json="$report_dir/$(basename "$container_json")"
cp "$container_json" "$latest_json"

python3 benchmark/reporting/analyze_request_gaps.py \
  --json-report "$latest_json" \
  --gunicorn-log "$gunicorn_log" \
  --server-exception-log "$exception_log" \
  --docker-stats-csv "$docker_stats_csv" \
  --runtime-config-json "$runtime_config" \
  --output-json "$latest_json" \
  --skip-md || true

python3 benchmark/reporting/analyze_gthread_queue.py \
  --json-report "$latest_json" \
  --queue-log "$queue_log"

readme_path="${latest_json%.json}_README.md"
python3 benchmark/reporting/build_benchmark_readme_report.py accurate \
  --json-report "$latest_json" \
  --output-md "$readme_path"

# Remove the temporary env copy. It can contain secrets inherited from root .env.
rm -f "$runtime_env_file"

restore_normal_services
restore_needed=false
cleanup_benchmark_container
trap - EXIT

echo
echo "Accurate timing benchmark complete."
echo "JSON report:   $latest_json"
echo "README report: $readme_path"

exit "$runner_exit"
