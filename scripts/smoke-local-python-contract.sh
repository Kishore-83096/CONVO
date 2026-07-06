#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

identity_base_url="http://127.0.0.1:5000"
messenger_base_url="http://127.0.0.1:8000"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --identity-base-url) identity_base_url="${2%/}"; shift 2 ;;
    --messenger-base-url) messenger_base_url="${2%/}"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--identity-base-url URL] [--messenger-base-url URL]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

tmpdir="$(mktemp -d)"

json_field() {
  local file="$1" expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
cur = obj
for part in sys.argv[2].split("."):
    cur = cur[part]
print(cur)
PY
}

request_json() {
  local method="$1" url="$2" body="${3:-}" token="${4:-}" out="$5"
  local status
  local curl_args=(-sS -o "$out" -w '%{http_code}' -X "$method" "$url" -H 'Content-Type: application/json')
  if [[ -n "$token" ]]; then
    curl_args+=(-H "Authorization: Bearer $token")
  fi
  if [[ -n "$body" ]]; then
    curl_args+=(--data "$body")
  else
    :
  fi
  status="$(curl "${curl_args[@]}")"
  if [[ ! "$status" =~ ^2 ]]; then
    printf '\n[FAIL] Request failed: %s %s\nStatus: %s\nResponse body:\n' "$method" "$url" "$status" >&2
    cat "$out" >&2
    exit 1
  fi
}

delete_user() {
  local token="$1" user_file="$2" password="$3" label="$4"
  local username email contact_number body out
  username="$(json_field "$user_file" username)"
  email="$(python3 - "$user_file" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("email") or "")
PY
)"
  contact_number="$(json_field "$user_file" contact_number)"
  body="$(python3 - "$username" "$email" "$contact_number" "$password" <<'PY'
import json, sys
print(json.dumps({"username": sys.argv[1], "email": sys.argv[2], "contact_number": sys.argv[3], "current_password": sys.argv[4]}))
PY
)"
  out="$tmpdir/delete_${label}.json"
  if request_json DELETE "$identity_base_url/api/v1/auth/delete-account" "$body" "$token" "$out"; then
    pass "Deleted temporary user $label"
  fi
}

run_id="$(date -u +%Y%m%d%H%M%S)$((100 + RANDOM % 900))"
password="SmokeTest@12345"
user_a="smokea${run_id}"
user_b="smokeb${run_id}"
token_a=""
token_b=""

cleanup() {
  info "Cleanup starting"
  if [[ -n "$token_a" && -f "$tmpdir/user_a.json" ]]; then
    delete_user "$token_a" "$tmpdir/user_a.json" "$password" A || warn "Could not delete temporary user A"
  fi
  if [[ -n "$token_b" && -f "$tmpdir/user_b.json" ]]; then
    delete_user "$token_b" "$tmpdir/user_b.json" "$password" B || warn "Could not delete temporary user B"
  fi
  pass "Cleanup completed"
  rm -rf "$tmpdir"
}
trap cleanup EXIT

info "Checking Identity health"
curl -fsS "$identity_base_url/api/v1/health/" >/dev/null
pass "Identity health OK"

info "Checking Messenger health"
curl -fsS "$messenger_base_url/api/v1/health/" >/dev/null
pass "Messenger health OK"

info "Registering temporary Identity users"
body_a="$(python3 - "$user_a" "$password" <<'PY'
import json, sys
print(json.dumps({"full_name": "Smoke Test A", "username": sys.argv[1], "password": sys.argv[2], "confirm_password": sys.argv[2]}))
PY
)"
body_b="$(python3 - "$user_b" "$password" <<'PY'
import json, sys
print(json.dumps({"full_name": "Smoke Test B", "username": sys.argv[1], "password": sys.argv[2], "confirm_password": sys.argv[2]}))
PY
)"
request_json POST "$identity_base_url/api/v1/auth/register" "$body_a" "" "$tmpdir/register_a.json"
request_json POST "$identity_base_url/api/v1/auth/register" "$body_b" "" "$tmpdir/register_b.json"
python3 - "$tmpdir/register_a.json" "$tmpdir/user_a.json" <<'PY'
import json, sys
json.dump(json.load(open(sys.argv[1]))["data"], open(sys.argv[2], "w"))
PY
python3 - "$tmpdir/register_b.json" "$tmpdir/user_b.json" <<'PY'
import json, sys
json.dump(json.load(open(sys.argv[1]))["data"], open(sys.argv[2], "w"))
PY
pass "Registered user A: $(json_field "$tmpdir/user_a.json" username), contact_number=$(json_field "$tmpdir/user_a.json" contact_number)"
pass "Registered user B: $(json_field "$tmpdir/user_b.json" username), contact_number=$(json_field "$tmpdir/user_b.json" contact_number)"

info "Logging in temporary users"
login_body_a="$(python3 - "$user_a" "$password" <<'PY'
import json, sys
print(json.dumps({"method": "username", "identifier": sys.argv[1], "password": sys.argv[2]}))
PY
)"
login_body_b="$(python3 - "$user_b" "$password" <<'PY'
import json, sys
print(json.dumps({"method": "username", "identifier": sys.argv[1], "password": sys.argv[2]}))
PY
)"
request_json POST "$identity_base_url/api/v1/auth/login" "$login_body_a" "" "$tmpdir/login_a.json"
request_json POST "$identity_base_url/api/v1/auth/login" "$login_body_b" "" "$tmpdir/login_b.json"
token_a="$(json_field "$tmpdir/login_a.json" data.access_token)"
token_b="$(json_field "$tmpdir/login_b.json" data.access_token)"
[[ -n "$token_a" && -n "$token_b" ]] || die "Login did not return access tokens"
pass "Login returned access tokens"

info "Checking Messenger JWT verification using /api/v1/auth/whoami/"
request_json GET "$messenger_base_url/api/v1/auth/whoami/" "" "$token_a" "$tmpdir/whoami_a.json"
authenticated="$(json_field "$tmpdir/whoami_a.json" authenticated)"
[[ "$authenticated" == "True" || "$authenticated" == "true" ]] || die "Messenger whoami did not authenticate user A"
pass "Messenger accepted Identity JWT for user_id=$(json_field "$tmpdir/whoami_a.json" user_id)"

info "Adding user B as contact of user A through Identity"
contact_number="$(json_field "$tmpdir/user_b.json" contact_number)"
contact_body="$(python3 - "$contact_number" <<'PY'
import json, sys
print(json.dumps({"contact_number": sys.argv[1], "saved_name": "Smoke Contact B"}))
PY
)"
request_json POST "$identity_base_url/api/v1/contacts" "$contact_body" "$token_a" "$tmpdir/add_contact.json"
contact_id="$(json_field "$tmpdir/add_contact.json" data.id)"
pass "Contact added in Identity. contact_id=$contact_id"

info "Blocking contact to verify Identity -> Messenger policy sync"
request_json PATCH "$identity_base_url/api/v1/contacts/$contact_id/block" '{"is_blocked":true}' "$token_a" "$tmpdir/block.json"
pass "Block policy synced successfully"

info "Unblocking contact"
request_json PATCH "$identity_base_url/api/v1/contacts/$contact_id/block" '{"is_blocked":false}' "$token_a" "$tmpdir/unblock.json"
pass "Unblock policy synced successfully"

info "Ghosting contact to verify ghost policy sync"
request_json PATCH "$identity_base_url/api/v1/contacts/$contact_id/ghost" '{"is_ghosted":true,"duration":"1h"}' "$token_a" "$tmpdir/ghost.json"
pass "Ghost policy synced successfully"

info "Unghosting contact"
request_json PATCH "$identity_base_url/api/v1/contacts/$contact_id/ghost" '{"is_ghosted":false,"duration":"1h"}' "$token_a" "$tmpdir/unghost.json"
pass "Unghost policy synced successfully"

pass "Local Python Identity <-> Messenger smoke test PASSED"
