#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

info() { printf '\n==> %s\n' "$*"; }
pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
fail() { printf '[FAIL] %s\n' "$*" >&2; }
die() { fail "$*"; exit 1; }

usage_error() {
  printf 'Error: %s\n' "$*" >&2
  exit 2
}

abs_path() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$PWD" "$path"
  fi
}

resolve_root() {
  local root="${1:-$repo_root}"
  cd "$root"
  pwd
}

require_file() {
  [[ -f "$1" ]] || die "Missing file: $1"
}

require_dir() {
  [[ -d "$1" ]] || die "Missing directory: $1"
}

remove_report_artifact_dir() {
  local report_dir="$1"
  local artifact_dir="$2"

  [[ -d "$artifact_dir" ]] || return 0

  local report_abs
  local artifact_abs
  local artifact_parent
  local artifact_base
  report_abs="$(cd "$report_dir" && pwd)"
  artifact_abs="$(cd "$artifact_dir" && pwd)"
  artifact_parent="$(dirname "$artifact_abs")"
  artifact_base="$(basename "$artifact_abs")"

  if [[ "$artifact_parent" != "$report_abs" || "$artifact_base" != .*_artifacts ]]; then
    warn "Refusing to delete unexpected artifact directory: $artifact_abs"
    return 1
  fi

  rm -rf "$artifact_abs"
}

require_docker() {
  if [[ "${MYNA_DOCKER_READY_CHECKED:-}" == "1" ]]; then
    return
  fi

  if ! command -v docker >/dev/null 2>&1; then
    die "Docker CLI was not found. Install Docker Desktop or Docker Engine before running Docker benchmark scripts."
  fi

  local docker_error
  if ! docker_error="$(docker info 2>&1 >/dev/null)"; then
    die "Docker is not available from this shell. If you are using WSL 2, open Docker Desktop, enable Settings > Resources > WSL Integration for this distro, then restart this terminal. Docker said: ${docker_error}"
  fi

  export MYNA_DOCKER_READY_CHECKED=1
}

container_running() {
  require_docker
  local name="$1"
  [[ "$(docker ps --filter "name=^${name}$" --format '{{.Names}}')" == "$name" ]]
}

container_exists() {
  require_docker
  local name="$1"
  [[ "$(docker ps -a --filter "name=^${name}$" --format '{{.Names}}')" == "$name" ]]
}

remove_container_if_exists() {
  require_docker
  local name="$1"
  if container_exists "$name"; then
    docker rm -f "$name" >/dev/null
    warn "Removed old container: $name"
  fi
}

ensure_network() {
  require_docker
  local network="$1"
  if [[ "$(docker network ls --format '{{.Name}}' | awk -v n="$network" '$0 == n { print }')" != "$network" ]]; then
    docker network create "$network" >/dev/null
    pass "Created Docker network: $network"
  else
    pass "Docker network exists: $network"
  fi
}

wait_http_ok() {
  local name="$1"
  local url="$2"
  local max_attempts="${3:-60}"

  info "Waiting for ${name}: $url"
  for _ in $(seq 1 "$max_attempts"); do
    if curl -fsS --max-time 5 "$url" >/dev/null; then
      pass "$name is ready"
      return 0
    fi
    sleep 2
  done

  die "$name did not become ready at $url"
}

wait_mysql_ready() {
  local container="$1"
  local root_password="$2"

  info "Waiting for MySQL container: $container"
  for _ in $(seq 1 60); do
    if docker exec -e "MYSQL_PWD=$root_password" "$container" mysqladmin ping -h 127.0.0.1 -uroot --silent >/dev/null 2>&1; then
      pass "MySQL is ready"
      return 0
    fi
    sleep 2
  done

  docker logs "$container" --tail 100 || true
  die "MySQL did not become ready"
}

repair_benchmark_mysql_grants() {
  local container="$1"
  local root_password="$2"
  local benchmark_user="${3:-myna_benchmark}"
  local benchmark_password="${4:-myna_benchmark_password}"
  local identity_db="${5:-myna_identity_benchmark}"
  local messenger_db="${6:-myna_messenger_benchmark}"

  info "Repairing benchmark MySQL user grants"
  docker exec -i -e "MYSQL_PWD=$root_password" "$container" mysql -uroot <<SQL
CREATE DATABASE IF NOT EXISTS ${identity_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS ${messenger_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${benchmark_user}'@'%' IDENTIFIED BY '${benchmark_password}';
ALTER USER '${benchmark_user}'@'%' IDENTIFIED BY '${benchmark_password}';
GRANT ALL PRIVILEGES ON ${identity_db}.* TO '${benchmark_user}'@'%';
GRANT ALL PRIVILEGES ON ${messenger_db}.* TO '${benchmark_user}'@'%';
FLUSH PRIVILEGES;
SHOW GRANTS FOR '${benchmark_user}'@'%';
SQL
  pass "Benchmark MySQL grants are ready"
}

load_dotenv() {
  local path="$1"
  require_file "$path"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" == *=* ]] || continue
    local key="${line%%=*}"
    local value="${line#*=}"
    key="${key//[[:space:]]/}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < "$path"
}

dotenv_get() {
  local path="$1"
  local key="$2"
  python3 - "$path" "$key" <<'PY'
import sys
path, want = sys.argv[1], sys.argv[2]
for raw in open(path, encoding="utf-8-sig"):
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key.strip() == want:
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        print(value)
        raise SystemExit
PY
}

secret_fingerprint() {
  local value="${1:-}"
  if [[ -z "${value//[[:space:]]/}" ]]; then
    printf 'empty\n'
    return
  fi
  printf '%s' "$value" | sha256sum | awk '{ print substr($1, 1, 12) }'
}

latest_benchmark_json() {
  local dir="$1"
  find "$dir" -maxdepth 1 -type f -name '*.json' \
    ! -name '*cleanup*status*' ! -name '*request_gap*' \
    ! -name '*realtime_outbox_status*' \
    ! -name '*service_runtime_config*' \
    -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR == 1 { sub(/^[^ ]+ /, ""); print }'
}

python_cmd_for_messenger() {
  local messenger_root="$1"
  if [[ -x "$messenger_root/venv/bin/python" ]]; then
    printf '%s\n' "$messenger_root/venv/bin/python"
  elif [[ -x "$messenger_root/env/bin/python" ]]; then
    printf '%s\n' "$messenger_root/env/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    die "Could not find Python. Expected messenger/venv, messenger/env, python3, or python in PATH."
  fi
}
