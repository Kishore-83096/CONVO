#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
runner_env_file="messenger/.env.benchmark.runner.docker-network.local"
root_password="benchmark_root_password"
benchmark_password="myna_benchmark_password"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --runner-env-file) runner_env_file="$2"; shift 2 ;;
    --benchmark-mysql-root-password) root_password="$2"; shift 2 ;;
    --benchmark-mysql-password) benchmark_password="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--root PATH] [--runner-env-file PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"
report_dir="$PWD/benchmark/myna_api_test_reports"
mkdir -p "$report_dir"

info "Running Docker-network benchmark"
"$PWD/scripts/run-local-docker-network-benchmark.sh" --root "$PWD" --runner-env-file "$runner_env_file"

latest_json="$(latest_benchmark_json "$report_dir")"
[[ -n "$latest_json" ]] || die "No benchmark JSON report found after benchmark."
base="$(basename "$latest_json" .json)"
cleanup_status_path="$report_dir/${base}_host_side_messenger_cleanup_status.json"

info "Main JSON report: $(basename "$latest_json")"
info "Cleanup proof file: $(basename "$cleanup_status_path")"

"$PWD/scripts/cleanup-docker-mysql-benchmark-messenger.sh" \
  --root "$PWD" \
  --status-output-path "$cleanup_status_path" \
  --benchmark-mysql-root-password "$root_password" \
  --benchmark-mysql-password "$benchmark_password"

"$PWD/scripts/patch-latest-benchmark-report-with-cleanup.sh" --root "$PWD" --cleanup-status-path "$cleanup_status_path"
"$PWD/scripts/repair-latest-benchmark-report-pair.sh" --root "$PWD"

pass "Benchmark + verified Messenger cleanup succeeded"
