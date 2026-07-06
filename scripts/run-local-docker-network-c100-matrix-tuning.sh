#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
runner_env_file="messenger/.env.benchmark.runner.docker-network.local"
identity_env_file="identity_service/env/identity.benchmark.env"
messenger_env_file="messenger/env/messenger.benchmark.env"
report_dir="benchmark/myna_api_test_reports"
docker_stats_interval_ms=2000
stop_on_run_failure=0
cleanup_artifacts=true
web_concurrency_values="6"
asgi_thread_values="12"
backlog_values="4096"
pair_count=100
benchmark_levels="1,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100"
matrix_repetitions="${MATRIX_REPETITIONS:-1}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --runner-env-file) runner_env_file="$2"; shift 2 ;;
    --identity-env-file) identity_env_file="$2"; shift 2 ;;
    --messenger-env-file) messenger_env_file="$2"; shift 2 ;;
    --report-dir) report_dir="$2"; shift 2 ;;
    --docker-stats-interval-milliseconds) docker_stats_interval_ms="$2"; shift 2 ;;
    --web-concurrency-values) web_concurrency_values="$2"; shift 2 ;;
    --asgi-thread-values) asgi_thread_values="$2"; shift 2 ;;
    --backlog-values) backlog_values="$2"; shift 2 ;;
    --pair-count) pair_count="$2"; shift 2 ;;
    --benchmark-levels) benchmark_levels="$2"; shift 2 ;;
    --matrix-repetitions) matrix_repetitions="$2"; shift 2 ;;
    --stop-on-run-failure) stop_on_run_failure=1; shift ;;
    --keep-artifacts) cleanup_artifacts=false; shift ;;
    -h|--help)
      cat <<EOF
Usage: $0 [options]

Runs a Docker-network accurate-timing tuning matrix for concurrency levels up
to 100 with 100 distributed pairs. Each matrix run writes temporary raw
artifacts, then one combined README summary is generated.

Options:
  --web-concurrency-values CSV     Default: 6,8,10
  --asgi-thread-values CSV         Default: 12
  --backlog-values CSV             Default: 4096
  --pair-count N                   Default: 100
  --benchmark-levels CSV           Default: 1,5,10,15,...,100
  --matrix-repetitions N           Default: 1
  --stop-on-run-failure            Stop the matrix when one run fails.
  --keep-artifacts                 Keep raw JSON/log/CSV artifacts after README generation.
EOF
      exit 0
      ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"
[[ -f "$identity_env_file" ]] || identity_env_file="identity_service/.env.benchmark.mysql-docker.local"
[[ -f "$messenger_env_file" ]] || messenger_env_file="messenger/.env.benchmark.mysql-docker.local"

resolved_report_dir="$(abs_path "$report_dir")"
mkdir -p "$resolved_report_dir"
stamp="$(date +%H-%M-%S_%Y-%m-%d)"
metadata_dir="$resolved_report_dir/.c100_matrix_tuning_${stamp}_artifacts"
mkdir -p "$metadata_dir"

csv_to_array() {
  local csv="$1"
  local -n out="$2"
  IFS=',' read -r -a out <<<"$csv"
}

csv_to_array "$web_concurrency_values" web_values
csv_to_array "$asgi_thread_values" thread_values
csv_to_array "$backlog_values" backlog_array

common_runner=(
  "MYNA_BENCHMARK_LEVELS=$benchmark_levels"
  "MYNA_DISTRIBUTED_PAIR_COUNT=$pair_count"
  MYNA_WARMUP_ALL_PAIRS=true
  MYNA_CONNECTION_WARMUP_ENABLED=true
  MYNA_CONNECTION_WARMUP_CONCURRENCY=100
  MYNA_HTTP_MAX_CONNECTIONS=300
  MYNA_HTTP_MAX_KEEPALIVE_CONNECTIONS=300
  MYNA_HTTP_KEEPALIVE_EXPIRY_SECONDS=60
  MYNA_HTTP_POOL_TIMEOUT_SECONDS=10
  MYNA_BENCHMARK_COOLDOWN_SECONDS=3
  MYNA_REQUEST_TIMEOUT_SECONDS=30
  MYNA_STOP_ON_FIRST_FAILED_LEVEL=false
  MYNA_CLEANUP_MESSENGER_DJANGO=true
  MYNA_CLEANUP_DB_RETRY_ATTEMPTS=8
  MYNA_CLEANUP_DB_RETRY_DELAY_SECONDS=3
  MYNA_CLEANUP_IDENTITY_USERS=true
  MYNA_RUNNER_PATH=docker-network
)

common_messenger=(
  MESSENGER_PROCESS_ROLE=http
  MESSENGER_HTTP_SERVER_MODE=asgi
  GUNICORN_TIMEOUT=60
  GUNICORN_GRACEFUL_TIMEOUT=30
  GUNICORN_KEEP_ALIVE=5
  GUNICORN_MAX_REQUESTS=1000
  GUNICORN_MAX_REQUESTS_JITTER=100
)

metadata_paths=()
run_index=0
stop_requested=0
if ! [[ "$matrix_repetitions" =~ ^[0-9]+$ ]] || [[ "$matrix_repetitions" -lt 1 ]]; then
  usage_error "--matrix-repetitions must be a positive integer."
fi
total_runs=$((${#web_values[@]} * ${#thread_values[@]} * ${#backlog_array[@]} * matrix_repetitions))

for web in "${web_values[@]}"; do
  for asgi_threads in "${thread_values[@]}"; do
    for backlog in "${backlog_array[@]}"; do
      for repetition in $(seq 1 "$matrix_repetitions"); do
        run_index=$((run_index + 1))
        repetition_suffix=""
        repetition_label=""
        if [[ "$matrix_repetitions" -gt 1 ]]; then
          repetition_suffix="_r${repetition}"
          repetition_label=" repetition ${repetition}/${matrix_repetitions}"
        fi
        label="C100 matrix ${run_index}/${total_runs}: web=$web asgi_threads=$asgi_threads backlog=$backlog${repetition_label}"
        slug="c100_w${web}_t${asgi_threads}_b${backlog}${repetition_suffix}"
        metadata_path="$metadata_dir/${slug}.run.json"
        metadata_paths+=("$metadata_path")
        test_run_id="myna-c100-$(printf '%s' "$stamp" | tr -cd '[:alnum:]')-$slug"

        messenger_env=("WEB_CONCURRENCY=$web" "ASGI_THREADS=$asgi_threads" "GUNICORN_BACKLOG=$backlog" "${common_messenger[@]}")
        messenger_env+=("DB_CONN_MAX_AGE=0" "DB_CONN_HEALTH_CHECKS=true")
        runner_env=("MYNA_REPORT_FILE_PREFIX=myna_docker_dns_c100_matrix_$slug" "MYNA_TEST_RUN_ID=$test_run_id" "${common_runner[@]}")
        args=(
          --root "$PWD"
          --runner-env-file "$runner_env_file"
          --identity-env-file "$identity_env_file"
          --messenger-env-file "$messenger_env_file"
          --report-dir "$report_dir"
          --docker-stats-interval-milliseconds "$docker_stats_interval_ms"
          --run-label "$label"
          --run-metadata-output-path "$metadata_path"
          --skip-readme
        )

        for item in "${messenger_env[@]}"; do args+=(--messenger-env "$item"); done
        for item in "${runner_env[@]}"; do args+=(--runner-env "$item"); done

        info "Running $label"
        printf '  WEB_CONCURRENCY=%s\n  ASGI_THREADS=%s\n  GUNICORN_BACKLOG=%s\n  DB_CONN_MAX_AGE=0\n  REPETITION=%s/%s\n' "$web" "$asgi_threads" "$backlog" "$repetition" "$matrix_repetitions"
        if ! "$PWD/scripts/run-local-docker-network-benchmark-accurate-timing.sh" "${args[@]}"; then
          warn "Run failed: $label"
          if [[ "$stop_on_run_failure" -eq 1 ]]; then
            stop_requested=1
            break 4
          fi
        fi
      done
    done
  done
done

manifest_path="$metadata_dir/c100_matrix_tuning_runs.json"
python3 - "$manifest_path" "${metadata_paths[@]}" <<'PY'
import datetime
import json
import sys

runs = []
for path in sys.argv[2:]:
    try:
        runs.append(json.load(open(path, encoding="utf-8")))
    except FileNotFoundError:
        runs.append({"benchmark_succeeded": False, "benchmark_error": f"Missing metadata: {path}"})

json.dump(
    {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "report_type": "c100_matrix_tuning",
        "runs": runs,
    },
    open(sys.argv[1], "w", encoding="utf-8"),
    indent=2,
)
PY

matrix_has_failed_runs="$(python3 - "$manifest_path" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
failed = any(
    run.get("benchmark_succeeded") is not True
    or int(run.get("analyzer_exit_code") or 0) != 0
    for run in manifest.get("runs", [])
)
print("true" if failed else "false")
PY
)"

combined_report_path="$resolved_report_dir/${stamp}_c100_matrix_tuning_README.md"
matrix_readme_args=(matrix --runs-manifest "$manifest_path" --output-md "$combined_report_path")
if [[ "$cleanup_artifacts" == true ]]; then
  matrix_readme_args+=(--omit-source-paths)
fi
python3 ./scripts/build-benchmark-readme-report.py "${matrix_readme_args[@]}"

validation_path="$metadata_dir/c100_matrix_tuning_validation.json"
expected_run_count="${#metadata_paths[@]}"
set +e
python3 ./scripts/validate-c100-matrix-tuning-report.py \
  --runs-manifest "$manifest_path" \
  --report-md "$combined_report_path" \
  --output-json "$validation_path" \
  --expected-run-count "$expected_run_count" \
  --best-concurrency 100
validation_exit=$?
set -e
if [[ "$validation_exit" -ne 0 ]]; then
  warn "Matrix README validation reported issues. Exit code: $validation_exit"
fi

artifact_dirs=()
while IFS= read -r artifact_dir; do
  [[ -n "$artifact_dir" ]] && artifact_dirs+=("$artifact_dir")
done < <(python3 - "$manifest_path" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
dirs = {
    str(Path(run["json_report_path"]).parent)
    for run in manifest.get("runs", [])
    if run.get("json_report_path")
}
for item in sorted(dirs):
    print(item)
PY
)

artifact_status="$metadata_dir"
if [[ "$cleanup_artifacts" == true ]]; then
  for artifact_dir in "${artifact_dirs[@]}"; do
    remove_report_artifact_dir "$resolved_report_dir" "$artifact_dir"
  done
  remove_report_artifact_dir "$resolved_report_dir" "$metadata_dir"
  artifact_status="deleted after README generation"
elif [[ "$matrix_has_failed_runs" == true ]]; then
  artifact_status="$metadata_dir (kept because --keep-artifacts was used)"
fi

pass "C100 matrix tuning complete"
printf '  Matrix README report:               %s\n' "$combined_report_path"
printf '  Raw artifacts:                      %s\n' "$artifact_status"
if [[ "$stop_requested" -eq 1 ]]; then
  die "Matrix stopped after first failed run. README was generated."
fi
