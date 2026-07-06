#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--root PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"

identity_env="identity_service/.env.local"
messenger_env="messenger/.env.local"
has_failure=0

check_file() {
  if [[ -f "$1" ]]; then pass "Found $1"; else fail "Missing $1"; has_failure=1; fi
}

require_key() {
  local file="$1" key="$2" label="$3"
  local value
  value="$(dotenv_get "$file" "$key" || true)"
  if [[ -z "${value//[[:space:]]/}" ]]; then
    fail "$label is missing or empty: $key"
    has_failure=1
  else
    pass "$label contains $key"
  fi
}

check_exact() {
  local file="$1" key="$2" expected="$3" label="$4"
  local actual
  actual="$(dotenv_get "$file" "$key" || true)"
  if [[ "$actual" == "$expected" ]]; then
    pass "$label.$key = $expected"
  else
    fail "$label.$key should be '$expected' but is '$actual'"
    has_failure=1
  fi
}

check_any() {
  local file="$1" key="$2" label="$3"; shift 3
  local actual allowed
  actual="$(dotenv_get "$file" "$key" || true)"
  for allowed in "$@"; do
    if [[ "$actual" == "$allowed" ]]; then
      pass "$label.$key = $actual"
      return
    fi
  done
  fail "$label.$key should be one of '$*' but is '$actual'"
  has_failure=1
}

check_starts_with() {
  local file="$1" key="$2" prefix="$3" label="$4"
  local actual
  actual="$(dotenv_get "$file" "$key" || true)"
  if [[ "$actual" == "$prefix"* ]]; then
    pass "$label.$key starts with $prefix"
  else
    fail "$label.$key should start with '$prefix' but is '$actual'"
    has_failure=1
  fi
}

compare_secret() {
  local left_file="$1" left_key="$2" left_label="$3" right_file="$4" right_key="$5" right_label="$6"
  local left right
  left="$(dotenv_get "$left_file" "$left_key" || true)"
  right="$(dotenv_get "$right_file" "$right_key" || true)"
  if [[ -z "${left//[[:space:]]/}" || -z "${right//[[:space:]]/}" ]]; then
    fail "$left_label.$left_key or $right_label.$right_key is empty"
    has_failure=1
  elif [[ "$left" == "$right" ]]; then
    pass "$left_label.$left_key matches $right_label.$right_key fingerprint=$(secret_fingerprint "$left")"
  else
    fail "$left_label.$left_key does NOT match $right_label.$right_key"
    printf '       %s fingerprint : %s\n' "$left_label" "$(secret_fingerprint "$left")"
    printf '       %s fingerprint: %s\n' "$right_label" "$(secret_fingerprint "$right")"
    has_failure=1
  fi
}

info "Myna local env contract checker"
printf 'Root: %s\n' "$PWD"

check_file "$identity_env"
check_file "$messenger_env"
if [[ "$has_failure" -ne 0 ]]; then
  warn "Create missing .env.local files from templates first."
  exit 1
fi

info "Checking required Identity keys"
for key in APP_ENV DATABASE_URL SECRET_KEY JWT_SECRET_KEY MESSENGER_SERVICE_BASE_URL MESSENGER_INTERNAL_SECRET; do
  require_key "$identity_env" "$key" "identity_service/.env.local"
done

info "Checking required Messenger keys"
for key in APP_ENV DJANGO_SECRET_KEY DATABASE_URL IDENTITY_SERVICE_BASE_URL MESSENGER_SERVICE_BASE_URL JWT_VERIFYING_KEY CONTACT_POLICY_SYNC_SECRET REDIS_URL; do
  require_key "$messenger_env" "$key" "messenger/.env.local"
done

info "Checking shared secrets without printing them"
compare_secret "$identity_env" JWT_SECRET_KEY identity_service "$messenger_env" JWT_VERIFYING_KEY messenger
compare_secret "$identity_env" MESSENGER_INTERNAL_SECRET identity_service "$messenger_env" CONTACT_POLICY_SYNC_SECRET messenger

info "Checking local Python service URLs"
check_any "$identity_env" APP_ENV identity_service local development
check_any "$messenger_env" APP_ENV messenger local development
check_exact "$identity_env" MESSENGER_SERVICE_BASE_URL "http://127.0.0.1:8000" identity_service
check_exact "$messenger_env" IDENTITY_SERVICE_BASE_URL "http://127.0.0.1:5000/api/v1" messenger
check_exact "$messenger_env" MESSENGER_SERVICE_BASE_URL "http://127.0.0.1:8000" messenger
check_exact "$messenger_env" REDIS_URL "redis://127.0.0.1:6379/0" messenger

info "Checking database URL style"
check_starts_with "$identity_env" DATABASE_URL mysql identity_service
check_starts_with "$messenger_env" DATABASE_URL mysql messenger

info "Secret fingerprints only, safe to paste"
printf 'identity JWT_SECRET_KEY fingerprint              : %s\n' "$(secret_fingerprint "$(dotenv_get "$identity_env" JWT_SECRET_KEY || true)")"
printf 'messenger JWT_VERIFYING_KEY fingerprint          : %s\n' "$(secret_fingerprint "$(dotenv_get "$messenger_env" JWT_VERIFYING_KEY || true)")"
printf 'identity MESSENGER_INTERNAL_SECRET fingerprint   : %s\n' "$(secret_fingerprint "$(dotenv_get "$identity_env" MESSENGER_INTERNAL_SECRET || true)")"
printf 'messenger CONTACT_POLICY_SYNC_SECRET fingerprint : %s\n' "$(secret_fingerprint "$(dotenv_get "$messenger_env" CONTACT_POLICY_SYNC_SECRET || true)")"

if [[ "$has_failure" -ne 0 ]]; then
  die "Local env contract check FAILED. Fix the failed values and run again."
fi

pass "Local env contract check PASSED"
