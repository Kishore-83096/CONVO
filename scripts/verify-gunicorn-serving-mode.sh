#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

identity_container="identity-service-local"
messenger_container="messenger-service-local"
expected_identity_workers=4
expected_identity_threads=8
expected_messenger_workers=4
expected_messenger_asgi_threads=8
expected_backlog="4096"
expected_timeout="60"
expected_graceful_timeout="30"
expected_keep_alive="5"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --identity-container) identity_container="$2"; shift 2 ;;
    --messenger-container) messenger_container="$2"; shift 2 ;;
    --expected-identity-workers) expected_identity_workers="$2"; shift 2 ;;
    --expected-identity-threads) expected_identity_threads="$2"; shift 2 ;;
    --expected-messenger-workers) expected_messenger_workers="$2"; shift 2 ;;
    --expected-messenger-asgi-threads) expected_messenger_asgi_threads="$2"; shift 2 ;;
    --expected-backlog) expected_backlog="$2"; shift 2 ;;
    --expected-timeout) expected_timeout="$2"; shift 2 ;;
    --expected-graceful-timeout) expected_graceful_timeout="$2"; shift 2 ;;
    --expected-keep-alive) expected_keep_alive="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [options]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

check_container_env() {
  local container="$1" service="$2" key value display expected
  info "Checking env values: $service / $container"
  for key in WEB_CONCURRENCY ASGI_THREADS GUNICORN_THREADS GUNICORN_BACKLOG GUNICORN_TIMEOUT GUNICORN_GRACEFUL_TIMEOUT GUNICORN_KEEP_ALIVE DATABASE_URL SQLALCHEMY_DATABASE_URI IDENTITY_SERVICE_BASE_URL MESSENGER_SERVICE_BASE_URL REDIS_URL; do
    if value="$(docker exec "$container" printenv "$key" 2>/dev/null)"; then
      display="$value"
      if [[ "$key" =~ DATABASE_URL|SQLALCHEMY_DATABASE_URI ]]; then
        display="$(printf '%s' "$display" | sed -E 's#://([^:]+):([^@]+)@#://\1:***@#')"
      fi
      expected=""
      case "$service:$key" in
        Identity:WEB_CONCURRENCY) expected="$expected_identity_workers" ;;
        Identity:GUNICORN_THREADS) expected="$expected_identity_threads" ;;
        Identity:GUNICORN_BACKLOG) expected="$expected_backlog" ;;
        Identity:GUNICORN_TIMEOUT) expected="$expected_timeout" ;;
        Identity:GUNICORN_GRACEFUL_TIMEOUT) expected="$expected_graceful_timeout" ;;
        Identity:GUNICORN_KEEP_ALIVE) expected="$expected_keep_alive" ;;
        Messenger:WEB_CONCURRENCY) expected="$expected_messenger_workers" ;;
        Messenger:ASGI_THREADS) expected="$expected_messenger_asgi_threads" ;;
        Messenger:GUNICORN_BACKLOG) expected="$expected_backlog" ;;
        Messenger:GUNICORN_TIMEOUT) expected="$expected_timeout" ;;
        Messenger:GUNICORN_GRACEFUL_TIMEOUT) expected="$expected_graceful_timeout" ;;
        Messenger:GUNICORN_KEEP_ALIVE) expected="$expected_keep_alive" ;;
      esac
      if [[ -n "$expected" && "$value" != "$expected" ]]; then
        die "$service $key expected $expected but got $display"
      fi
      pass "$key=$display"
    else
      warn "MISS $key"
    fi
  done
}

check_gunicorn_process() {
  local container="$1" service="$2" app_marker="$3" expected_workers="$4" expected_threads="$5" should_use_threads="$6" should_use_backlog="$7" should_use_keep_alive="$8"
  local raw
  info "Checking Gunicorn runtime: $service / $container"
  raw="$(docker exec -i "$container" python - "$app_marker" <<'PY'
import glob, json, os, sys
app_marker = sys.argv[1]
processes = []
for path in glob.glob("/proc/[0-9]*/cmdline"):
    pid = int(path.split("/")[2])
    try:
        cmd = open(path, "rb").read().replace(b"\x00", b" ").decode("utf-8", "ignore").strip()
        ppid = int(open(f"/proc/{pid}/stat").read().split()[3])
    except Exception:
        continue
    if "gunicorn" in cmd and app_marker in cmd:
        processes.append({"pid": pid, "ppid": ppid, "cmd": cmd})
master = None
max_children = -1
for p in processes:
    child_count = sum(1 for x in processes if x["ppid"] == p["pid"])
    if child_count > max_children:
        max_children = child_count
        master = p
print(json.dumps({
    "process_count": len(processes),
    "worker_count": max_children if master else 0,
    "master_pid": master["pid"] if master else None,
    "master_cmd": master["cmd"] if master else "",
}))
PY
)"
  python3 - "$raw" "$service" "$expected_workers" "$expected_threads" "$should_use_threads" "$expected_timeout" "$expected_graceful_timeout" "$should_use_backlog" "$expected_backlog" "$should_use_keep_alive" "$expected_keep_alive" <<'PY'
import json, sys
raw, service, workers, threads, use_threads, timeout, graceful, use_backlog, backlog, use_keepalive, keepalive = sys.argv[1:]
data = json.loads(raw)
cmd = data["master_cmd"]
print(f"Gunicorn master PID: {data['master_pid']}")
print(f"Gunicorn total processes: {data['process_count']}")
print(f"Gunicorn worker count: {data['worker_count']}")
print("Gunicorn master command:")
print(cmd)
ok = True
def check(cond, good, bad):
    global ok
    if cond:
        print(f"[PASS] {good}")
    else:
        print(f"[FAIL] {bad}", file=sys.stderr)
        ok = False
check(int(data["worker_count"]) == int(workers), f"workers={workers}", f"expected workers={workers} but got {data['worker_count']}")
if use_threads == "true":
    check(f"--threads {threads}" in cmd, f"threads={threads}", f"threads {threads} not found in command")
check(f"--timeout {timeout}" in cmd, f"timeout={timeout}", f"timeout {timeout} not found in command")
check(f"--graceful-timeout {graceful}" in cmd, f"graceful-timeout={graceful}", f"graceful-timeout {graceful} not found in command")
if use_backlog == "true":
    check(f"--backlog {backlog}" in cmd, f"backlog={backlog}", f"backlog {backlog} not found in command")
if use_keepalive == "true":
    check(f"--keep-alive {keepalive}" in cmd, f"keep-alive={keepalive}", f"keep-alive {keepalive} not found in command")
if not ok:
    raise SystemExit(f"{service} Gunicorn runtime verification failed.")
print(f"{service} Gunicorn runtime verification passed.")
PY
}

container_running "$identity_container" || die "Identity container is not running: $identity_container"
container_running "$messenger_container" || die "Messenger container is not running: $messenger_container"

check_container_env "$identity_container" Identity
check_gunicorn_process "$identity_container" Identity "identity_service:app" "$expected_identity_workers" "$expected_identity_threads" true true true
check_container_env "$messenger_container" Messenger
check_gunicorn_process "$messenger_container" Messenger "messenger_config.asgi:application" "$expected_messenger_workers" "$expected_messenger_asgi_threads" false true true

messenger_asgi_threads="$(docker exec "$messenger_container" printenv ASGI_THREADS 2>/dev/null || true)"
[[ "$messenger_asgi_threads" == "$expected_messenger_asgi_threads" ]] || die "Messenger ASGI_THREADS expected $expected_messenger_asgi_threads but got ${messenger_asgi_threads:-missing}"
pass "Messenger ASGI_THREADS=$expected_messenger_asgi_threads"

pass "FINAL RESULT: serving env/runtime verification passed"
