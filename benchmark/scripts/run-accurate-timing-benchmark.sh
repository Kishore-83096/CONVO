#!/usr/bin/env bash
set -Eeuo pipefail

echo "==> BENCHMARK LAUNCHER V9.1: fail-closed + memory-bounded instrumentation"

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
    id="$(docker compose --env-file .env -f compose.yml ps -q "$service" 2>/dev/null || true)"
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
  docker compose --env-file .env -f compose.yml up -d --no-deps --force-recreate identity >/dev/null 2>&1 || true
  docker compose --env-file .env -f compose.yml up -d --no-deps --force-recreate messenger >/dev/null 2>&1 || true
}

show_setup_failure() {
  local service="$1"
  echo "ERROR: benchmark-mode setup failed for service: $service" >&2
  echo "==> Compose status" >&2
  docker compose --env-file .env -f compose.yml ps >&2 || true
  echo "==> $service logs (last 200 lines)" >&2
  docker compose --env-file .env -f compose.yml logs --tail 200 "$service" >&2 || true
}

container_env_value() {
  local container_id="$1"
  local key="$2"
  docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container_id" 2>/dev/null |     awk -F= -v wanted="$key" '$1 == wanted { sub(/^[^=]*=/, ""); print; exit }'
}

require_container_env() {
  local service="$1"
  local container_id="$2"
  local key="$3"
  local expected="$4"
  local actual
  actual="$(container_env_value "$container_id" "$key")"
  if [[ "$actual" != "$expected" ]]; then
    echo "ERROR: $service container env verification failed: $key" >&2
    echo "expected: $expected" >&2
    echo "actual:   ${actual:-<missing>}" >&2
    show_setup_failure "$service"
    return 1
  fi
}
benchmark_container_name="myna-accurate-timing-benchmark"
artifact_dir=""
stats_pid=""
stats_sampler_mode="not_started"
restore_needed=true
preserve_artifacts=false

cleanup_benchmark_container() {
  docker rm -f "$benchmark_container_name" >/dev/null 2>&1 || true
}

stop_host_docker_stats() {
  if [[ -n "${stats_pid:-}" ]]; then
    kill "$stats_pid" >/dev/null 2>&1 || true
    wait "$stats_pid" 2>/dev/null || true
    stats_pid=""
  fi
}

cleanup_current_run_artifacts() {
  if [[ "${preserve_artifacts:-false}" == "true" ]]; then
    return 0
  fi
  if [[ -n "${artifact_dir:-}" && -d "$artifact_dir" ]]; then
    rm -rf -- "$artifact_dir"
  fi
}

cleanup_on_exit() {
  stop_host_docker_stats
  cleanup_benchmark_container
  cleanup_current_run_artifacts
  if [[ "$restore_needed" == true ]]; then
    restore_normal_services
  fi
}

read_env_value() {
  local env_file="$1"
  local key="$2"
  awk -F= -v wanted="$key" '
    $1 == wanted {
      sub(/^[^=]*=/, "")
      print
      found = 1
      exit
    }
    END {
      if (!found) {
        print ""
      }
    }
  ' "$env_file"
}

on_error() {
  local status=$?
  local line="${BASH_LINENO[0]:-unknown}"
  local command="${BASH_COMMAND:-unknown}"
  echo "ERROR: benchmark launcher command failed" >&2
  echo "exit_status=$status" >&2
  echo "line=$line" >&2
  echo "command=$command" >&2
  return "$status"
}

trap on_error ERR
trap cleanup_on_exit EXIT INT TERM

# Start the canonical local architecture first.
./scripts/start-backend.sh

# Benchmark setup/cleanup intentionally creates and deletes many users. Recreate
# Identity with benchmark-only high local limits, and Messenger with direct-send
# profiling enabled. These overrides are process environment for Compose only and
# are not written back to .env.
echo "==> Enabling benchmark-only Identity rate limits and Messenger profiling"
echo "==> Recreating only identity for benchmark mode (--no-deps)"
if ! REGISTER_RATE_LIMIT='100000 per minute' \
  LOGIN_RATE_LIMIT='100000 per minute' \
  RESET_PASSWORD_RATE_LIMIT='100000 per minute' \
  DELETE_ACCOUNT_RATE_LIMIT='100000 per minute' \
  CONTACT_SEARCH_RATE_LIMIT='100000 per minute' \
  CONTACT_ADD_RATE_LIMIT='100000 per minute' \
  docker compose --env-file .env -f compose.yml up -d --no-deps --force-recreate identity; then
  show_setup_failure identity
  exit 1
fi
if ! wait_healthy identity; then
  show_setup_failure identity
  exit 1
fi
echo "==> Recreating only messenger for benchmark mode (--no-deps)"
if ! MYNA_PROFILE_DIRECT_SEND=true \
  MYNA_BENCHMARK_SKIP_DIRECT_ROOM_ACTIVITY_TOUCH=true \
  docker compose --env-file .env -f compose.yml up -d --no-deps --force-recreate messenger; then
  show_setup_failure messenger
  exit 1
fi

if ! wait_healthy messenger; then
  show_setup_failure messenger
  exit 1
fi

identity_id="$(docker compose --env-file .env -f compose.yml ps -q identity)"
messenger_id="$(docker compose --env-file .env -f compose.yml ps -q messenger)"
[[ -n "$identity_id" ]] || { show_setup_failure identity; exit 1; }
[[ -n "$messenger_id" ]] || { show_setup_failure messenger; exit 1; }

require_container_env identity "$identity_id" REGISTER_RATE_LIMIT '100000 per minute' || exit 1
require_container_env identity "$identity_id" DELETE_ACCOUNT_RATE_LIMIT '100000 per minute' || exit 1
require_container_env messenger "$messenger_id" MYNA_PROFILE_DIRECT_SEND 'true' || exit 1
require_container_env \
  messenger \
  "$messenger_id" \
  MYNA_BENCHMARK_SKIP_DIRECT_ROOM_ACTIVITY_TOUCH \
  'true' || exit 1
echo "==> Benchmark runtime overrides verified"

docker exec "$messenger_id" sh -c ': > /tmp/myna_benchmark_gunicorn_access.log; : > /tmp/myna_gthread_queue.log; : > /tmp/myna_benchmark_asgi_exceptions.jsonl' || true

report_dir="$repo_root/benchmark/reports"
mkdir -p "$report_dir"
# Remove generation-only leftovers from interrupted older runs. Final timestamped
# README files are preserved.
find "$report_dir" -mindepth 1 -maxdepth 1 -type d -name '.*_accurate_timing_artifacts' -exec rm -rf -- {} + 2>/dev/null || true
find "$report_dir" -maxdepth 1 -type f \
  \( -name '*.json' -o -name '*_request_gap_analysis.md' -o -name '*myna_accurate_timing*_README.md' \) \
  -delete 2>/dev/null || true
stamp="$(TZ=Asia/Kolkata date +%H-%M-%S_%Y-%m-%d)"
artifact_dir="$report_dir/.${stamp}_accurate_timing_artifacts"
container_report_stage="$artifact_dir/container-reports"
mkdir -p "$artifact_dir" "$container_report_stage"
runtime_env_file="$artifact_dir/runner.env"
gunicorn_log="$artifact_dir/${stamp}_gunicorn_access.log"
queue_log="$artifact_dir/${stamp}_gthread_queue.log"
exception_log="$artifact_dir/${stamp}_server_exceptions.jsonl"
runtime_config="$artifact_dir/${stamp}_runtime_config.json"
docker_stats_csv="$artifact_dir/${stamp}_docker_stats.csv"
printf 'timestamp,container,cpu_percent,mem_usage,mem_percent,net_io,block_io,pids\n' > "$docker_stats_csv"

python3 - "$repo_root/.env" "$runtime_env_file" "${runner_env[@]}" <<'PY'
from __future__ import annotations
import sys
import uuid
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
    "MYNA_TEST_RUN_ID": f"myna-dp-{uuid.uuid4().hex[:10]}",
}
values.update(fixed)
for item in overrides:
    key, value = item.split("=", 1)
    values[key] = value
out_path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
out_path.chmod(0o600)
PY

benchmark_run_id="$(read_env_value "$runtime_env_file" MYNA_TEST_RUN_ID)"
[[ -n "$benchmark_run_id" ]] || {
  echo "ERROR: generated runner env is missing MYNA_TEST_RUN_ID" >&2
  exit 1
}
stats_interval="$(read_env_value "$runtime_env_file" MYNA_DOCKER_STATS_INTERVAL_SECONDS)"
stats_interval="${stats_interval:-1}"
if ! [[ "$stats_interval" =~ ^[0-9]+([.][0-9]+)?$ ]] || ! awk -v value="$stats_interval" 'BEGIN { exit !(value > 0) }'; then
  echo "WARNING: invalid MYNA_DOCKER_STATS_INTERVAL_SECONDS=$stats_interval; using 1 second" >&2
  stats_interval=1
fi

start_host_docker_stats() {
  local container_ids=()
  local service id
  for service in messenger messenger-outbox identity messenger-postgres identity-postgres redis; do
    id="$(docker compose --env-file .env -f compose.yml ps -q "$service" 2>/dev/null || true)"
    [[ -n "$id" ]] && container_ids+=("$id")
  done

  if ((${#container_ids[@]} == 0)); then
    echo "WARNING: no Compose containers found for host Docker stats" >&2
    stats_sampler_mode="no_containers"
    return 0
  fi

  local api_sampler="$repo_root/benchmark/reporting/sample_host_docker_stats.py"
  if [[ -f "$api_sampler" && -S /var/run/docker.sock ]]; then
    echo "==> Recording host Docker stats for ${#container_ids[@]} containers every ${stats_interval}s via Docker Engine API one-shot sampling"
    python3 "$api_sampler" \
      --output-csv "$docker_stats_csv" \
      --interval "$stats_interval" \
      "${container_ids[@]}" &
    stats_pid=$!
    stats_sampler_mode="docker_engine_api_one_shot"
    sleep 0.15
    if kill -0 "$stats_pid" >/dev/null 2>&1; then
      return 0
    fi
    wait "$stats_pid" 2>/dev/null || true
    stats_pid=""
    echo "WARNING: Docker Engine API sampler exited early; falling back to docker stats --no-stream" >&2
  else
    echo "WARNING: Docker Engine API sampler/socket unavailable; falling back to docker stats --no-stream" >&2
  fi

  stats_sampler_mode="docker_cli_no_stream_fallback"
  echo "==> Recording fallback host Docker stats for ${#container_ids[@]} containers every ${stats_interval}s"
  (
    while true; do
      timestamp="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
      docker stats --no-stream --format '{{json .}}' "${container_ids[@]}" 2>/dev/null | \
        python3 -c '
import csv, json, sys
timestamp = sys.argv[1]
writer = csv.writer(sys.stdout)
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    try:
        row = json.loads(raw)
    except json.JSONDecodeError:
        continue
    writer.writerow([
        timestamp,
        row.get("Name") or row.get("Container") or row.get("ID") or "",
        str(row.get("CPUPerc") or "").rstrip("%"),
        row.get("MemUsage") or "",
        str(row.get("MemPerc") or "").rstrip("%"),
        row.get("NetIO") or "",
        row.get("BlockIO") or "",
        row.get("PIDs") or "",
    ])
' "$timestamp" >> "$docker_stats_csv" || true
      sleep "$stats_interval"
    done
  ) &
  stats_pid=$!
}

echo "==> Building the root benchmark runner image"
docker build -t myna-benchmark:local -f benchmark/Dockerfile .

runner_exit=0
echo "==> Running accurate-timing distributed-pairs benchmark inside Docker DNS network"
cleanup_benchmark_container
start_host_docker_stats
set +e
docker run \
  --name "$benchmark_container_name" \
  --network myna-local \
  --env-file "$runtime_env_file" \
  --env MYNA_REPORT_DIR=/tmp/myna-reports \
  --env MYNA_REPORT_ROOT=/tmp/myna-reports \
  myna-benchmark:local \
  /benchmark/runner/myna_distributed_pairs_latency_benchmark_test.py
runner_exit=$?
set -e
stop_host_docker_stats

echo "==> Copying benchmark reports out of the stopped runner container"
docker cp "$benchmark_container_name:/tmp/myna-reports/." "$container_report_stage/" 2>/dev/null || true
cleanup_benchmark_container

# The non-blocking queue collector writes through a background thread per Gunicorn
# worker. This short delay is outside measured traffic and lets queued log records flush.
sleep "${MYNA_GTHREAD_QUEUE_COLLECTOR_DRAIN_SECONDS:-1}"

docker cp "$messenger_id:/tmp/myna_benchmark_gunicorn_access.log" "$gunicorn_log" 2>/dev/null || : > "$gunicorn_log"
docker cp "$messenger_id:/tmp/myna_gthread_queue.log" "$queue_log" 2>/dev/null || : > "$queue_log"
docker cp "$messenger_id:/tmp/myna_benchmark_asgi_exceptions.jsonl" "$exception_log" 2>/dev/null || : > "$exception_log"

runtime_config_container=/tmp/myna_benchmark_runtime_config.json
docker exec -i "$messenger_id" python - <<'PY'
import json
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "messenger_config.settings")
import django

django.setup()
from django.conf import settings

payload = {
    "messenger": {
        "container": None,
        "env": settings.MESSENGER_RUNTIME_CONFIGURATION,
    }
}
Path("/tmp/myna_benchmark_runtime_config.json").write_text(
    json.dumps(payload, sort_keys=True),
    encoding="utf-8",
)
PY
docker cp "$messenger_id:$runtime_config_container" "$runtime_config"
python3 -m json.tool "$runtime_config" >/dev/null

container_json="$(python3 - "$container_report_stage" "$benchmark_run_id" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
expected_run_id = sys.argv[2]
candidates = []
for path in root.rglob("*.json"):
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        continue
    if obj.get("run_id") != expected_run_id:
        continue
    if isinstance(obj.get("summary"), dict) and isinstance(obj.get("cleanup"), dict):
        candidates.append(path)
if not candidates:
    raise SystemExit(1)
print(max(candidates, key=lambda p: p.stat().st_mtime))
PY
)" || {
  echo "Benchmark did not produce a current-run JSON report for run_id=$benchmark_run_id" >&2
  exit 1
}

latest_json="$report_dir/$(basename "$container_json")"
cp "$container_json" "$latest_json"

python3 - "$latest_json" "$docker_stats_csv" "$stats_sampler_mode" <<'PY'
import csv, json, sys
from pathlib import Path
report_path = Path(sys.argv[1])
stats_path = Path(sys.argv[2])
stats_sampler_mode = sys.argv[3]
report = json.loads(report_path.read_text(encoding="utf-8-sig"))
with stats_path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
    stats_rows = list(csv.DictReader(handle))
report["benchmark_launcher"] = {
    "version": "V9.1",
    "host_docker_stats_enabled": True,
    "host_docker_stats_sample_rows": len(stats_rows),
    "host_docker_stats_sampler_mode": stats_sampler_mode,
    "failure_readme_enabled": True,
    "intermediate_artifacts_deleted_after_readme": True,
}
report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
PY

request_gap_stdout="$artifact_dir/${stamp}_request_gap_analyzer.stdout.log"
request_gap_stderr="$artifact_dir/${stamp}_request_gap_analyzer.stderr.log"
set +e
python3 benchmark/reporting/analyze_request_gaps.py \
  --json-report "$latest_json" \
  --gunicorn-log "$gunicorn_log" \
  --server-exception-log "$exception_log" \
  --docker-stats-csv "$docker_stats_csv" \
  --runtime-config-json "$runtime_config" \
  --output-json "$latest_json" \
  --skip-md \
  >"$request_gap_stdout" \
  2>"$request_gap_stderr"
request_gap_exit=$?
set -e
if [[ "$request_gap_exit" -ne 0 ]]; then
  preserve_artifacts=true
  echo "ERROR: request-gap/server instrumentation analyzer failed with exit code $request_gap_exit" >&2
  if [[ "$request_gap_exit" -eq 137 || "$request_gap_exit" -eq 143 ]]; then
    echo "ERROR: analyzer was terminated by a signal; exit 137 commonly indicates SIGKILL/OOM." >&2
    echo "Raw JSON size: $(wc -c < "$latest_json") bytes" >&2
  fi
  cat "$request_gap_stderr" >&2 || true
  echo "Instrumentation artifacts preserved at: $artifact_dir" >&2
  exit "$request_gap_exit"
fi

python3 benchmark/reporting/analyze_gthread_queue.py \
  --json-report "$latest_json" \
  --queue-log "$queue_log"

# Request-level rows are required by the two analyzers above, but the final
# README consumes aggregated analysis only. Drop the massive raw request arrays
# before README generation to keep the final parse/write memory bounded.
python3 - "$latest_json" <<'PY'
import gc
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
with report_path.open("r", encoding="utf-8-sig") as handle:
    report = json.load(handle)

compacted_levels = 0
compacted_request_records = 0
for level in (report.get("benchmark") or {}).get("per_level") or []:
    records = level.pop("request_records", []) or []
    compacted_request_records += len(records)
    if records:
        compacted_levels += 1
    level["request_records_compacted_count"] = len(records)

report["instrumentation_compaction"] = {
    "raw_request_records_removed_after_correlation": True,
    "compacted_level_count": compacted_levels,
    "compacted_request_record_count": compacted_request_records,
}

gc.collect()
with report_path.open("w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, default=str)
    handle.write("\n")

print(json.dumps(report["instrumentation_compaction"], sort_keys=True))
PY

set +e
python3 - "$latest_json" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
report = json.loads(report_path.read_text(encoding="utf-8-sig"))
errors = []

gap = report.get("request_gap_analysis")
if not isinstance(gap, dict):
    errors.append("request_gap_analysis is missing")
else:
    matched = gap.get("matched_request_count")
    if not isinstance(matched, int) or matched <= 0:
        errors.append(f"matched_request_count is invalid: {matched!r}")

    host_stats = gap.get("host_docker_stats") or {}
    launcher_rows = int(
        (report.get("benchmark_launcher") or {}).get(
            "host_docker_stats_sample_rows", 0
        ) or 0
    )
    if launcher_rows > 0 and not host_stats.get("available"):
        errors.append(
            "host Docker stats were collected but request-gap analysis did not "
            "attach them"
        )

if report.get("service_runtime_config_parse_error"):
    errors.append(str(report["service_runtime_config_parse_error"]))

services = (report.get("effective_runtime_config") or {}).get("services")
if not isinstance(services, dict) or not services:
    errors.append("effective runtime service configuration is missing")

if errors:
    print("ERROR: benchmark instrumentation validation failed", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(2)
PY
instrumentation_validation_exit=$?
set -e
if [[ "$instrumentation_validation_exit" -ne 0 ]]; then
  preserve_artifacts=true
  echo "Instrumentation artifacts preserved at: $artifact_dir" >&2
  exit "$instrumentation_validation_exit"
fi

readme_stamp="$(TZ=Asia/Kolkata date +%H-%M-%S-%d-%m-%y)"
readme_path="$report_dir/${readme_stamp}_README.md"
python3 benchmark/reporting/build_benchmark_readme_report.py accurate \
  --json-report "$latest_json" \
  --output-md "$readme_path" \
  --omit-source-paths

# README generation succeeded. The JSON, queue/access logs, exception log,
# runtime config, docker-stats CSV, copied container reports, and runner env are
# generation-only artifacts for this run. Keep only the final README report.
echo "==> Final README generated; deleting current-run support artifacts"
rm -f "$latest_json"
rm -rf "$artifact_dir"

restore_normal_services
restore_needed=false
stop_host_docker_stats
cleanup_benchmark_container
cleanup_current_run_artifacts
trap - EXIT INT TERM

echo
if [[ "$runner_exit" -eq 0 ]]; then
  echo "Accurate timing benchmark complete."
else
  echo "Accurate timing benchmark FAILED; a failure README was generated."
fi
echo "README report: $readme_path"
echo "Intermediate report-generation artifacts: deleted"

exit "$runner_exit"
