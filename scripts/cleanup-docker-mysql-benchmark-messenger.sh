#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
status_output_path=""
root_password="benchmark_root_password"
benchmark_password="myna_benchmark_password"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --status-output-path) status_output_path="$2"; shift 2 ;;
    --benchmark-mysql-root-password) root_password="$2"; shift 2 ;;
    --benchmark-mysql-password) benchmark_password="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--root PATH] [--status-output-path PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"

write_status() {
  local success="$1" message="$2" stage="$3"
  [[ -z "$status_output_path" ]] && return 0
  mkdir -p "$(dirname "$status_output_path")"
  python3 - "$success" "$message" "$stage" "$status_output_path" <<'PY'
import datetime, json, sys
success = sys.argv[1] == "true"
status = {
    "attempted": True,
    "success": success,
    "cleanup_type": "host_side_messenger_cleanup",
    "cleanup_method": "drop_recreate_messenger_benchmark_database_and_rerun_migrations",
    "stage": sys.argv[3],
    "messenger_database": "myna_messenger_benchmark",
    "mysql_container": "mysql-benchmark-local",
    "messenger_container": "messenger-service-local",
    "message_data_removed": success,
    "all_messenger_benchmark_data_removed": success,
    "messages_created_by_benchmark_removed": success,
    "message": sys.argv[2],
    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
json.dump(status, open(sys.argv[4], "w", encoding="utf-8"), indent=2)
PY
}

trap 'code=$?; if [[ $code -ne 0 ]]; then write_status false "Messenger cleanup failed" failed; fi' EXIT

info "Cleaning Messenger benchmark messages/data from Docker MySQL"
for container in mysql-benchmark-local messenger-service-local; do
  container_running "$container" || die "Required container is not running: $container"
done

docker exec -i -e "MYSQL_PWD=$root_password" mysql-benchmark-local mysql -uroot <<SQL
DROP DATABASE IF EXISTS myna_messenger_benchmark;
CREATE DATABASE myna_messenger_benchmark CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'myna_benchmark'@'%' IDENTIFIED BY '${benchmark_password}';
ALTER USER 'myna_benchmark'@'%' IDENTIFIED BY '${benchmark_password}';
GRANT ALL PRIVILEGES ON myna_messenger_benchmark.* TO 'myna_benchmark'@'%';
FLUSH PRIVILEGES;
SHOW DATABASES LIKE 'myna_messenger_benchmark';
SQL
pass "Messenger benchmark database reset"

info "Re-running Messenger migrations after cleanup"
docker exec messenger-service-local python manage.py migrate --noinput
pass "Messenger migrations completed"

info "Checking Messenger health after cleanup"
curl -fsS --max-time 10 http://127.0.0.1:8000/api/v1/health/ >/dev/null
write_status true "Messenger benchmark messages/data removed successfully." completed
pass "Messenger cleanup completed successfully"
