#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
use_examples=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --use-examples) use_examples=1; shift ;;
    -h|--help) printf 'Usage: %s [--root PATH] [--use-examples]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"
has_failure=0

if [[ "$use_examples" -eq 1 ]]; then
  identity_env="identity_service/.env.production.example"
  messenger_env="messenger/.env.production.example"
  warn "Using .env.production.example files. Placeholder warnings are expected."
else
  identity_env="identity_service/.env.production"
  messenger_env="messenger/.env.production"
fi

require_file "$identity_env"
require_file "$messenger_env"

value_of() { dotenv_get "$1" "$2" || true; }
mark_fail() { fail "$1"; has_failure=1; }

require_key() {
  local file="$1" key="$2" label="$3" value
  value="$(value_of "$file" "$key")"
  if [[ -z "${value//[[:space:]]/}" ]]; then mark_fail "$label missing required key: $key"; else pass "$label contains $key"; fi
}

check_exact() {
  local file="$1" key="$2" expected="$3" label="$4" actual
  actual="$(value_of "$file" "$key")"
  if [[ "$actual" == "$expected" ]]; then pass "$label.$key = $expected"; else mark_fail "$label.$key should be '$expected' but is '$actual'"; fi
}

check_starts_with() {
  local file="$1" key="$2" prefix="$3" label="$4" actual
  actual="$(value_of "$file" "$key")"
  if [[ "$actual" == "$prefix"* ]]; then pass "$label.$key starts with $prefix"; else mark_fail "$label.$key should start with '$prefix' but is '$actual'"; fi
}

check_not_local() {
  local file="$1" key="$2" label="$3" actual bad
  actual="$(value_of "$file" "$key")"
  for bad in 127.0.0.1 localhost host.docker.internal identity-service-local messenger-service-local redis:6379; do
    if [[ "$actual" == *"$bad"* ]]; then
      mark_fail "$label.$key contains production-forbidden value '$bad': $actual"
      return
    fi
  done
  pass "$label.$key does not contain local/Docker-only hostnames"
}

compare_secret() {
  local left_file="$1" left_key="$2" left_label="$3" right_file="$4" right_key="$5" right_label="$6"
  local left right
  left="$(value_of "$left_file" "$left_key")"
  right="$(value_of "$right_file" "$right_key")"
  if [[ -z "${left//[[:space:]]/}" || -z "${right//[[:space:]]/}" ]]; then
    mark_fail "$left_label.$left_key or $right_label.$right_key is empty"
  elif [[ "$left" == "$right" ]]; then
    pass "$left_label.$left_key matches $right_label.$right_key fingerprint=$(secret_fingerprint "$left")"
  else
    mark_fail "$left_label.$left_key does NOT match $right_label.$right_key"
  fi
}

placeholder_warnings() {
  local file="$1" label="$2"
  python3 - "$file" "$label" <<'PY'
import sys
path, label = sys.argv[1], sys.argv[2]
for raw in open(path, encoding="utf-8-sig"):
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if "replace-" in value:
        print(f"[WARN] {label}.{key.strip()} still contains placeholder: {value.strip()}", file=sys.stderr)
PY
}

info "Myna production env contract checker"
printf 'Root: %s\nIdentity env: %s\nMessenger env: %s\n' "$PWD" "$identity_env" "$messenger_env"

info "Checking required Identity production keys"
for key in APP_ENV DATABASE_URL SECRET_KEY JWT_SECRET_KEY FRONTEND_ORIGINS MESSENGER_SERVICE_BASE_URL MESSENGER_INTERNAL_SECRET MESSENGER_POLICY_SYNC_REQUIRED; do
  require_key "$identity_env" "$key" identity_service
done

info "Checking required Messenger production keys"
for key in APP_ENV DJANGO_SECRET_KEY DJANGO_DEBUG DJANGO_ALLOWED_HOSTS DJANGO_CSRF_TRUSTED_ORIGINS FRONTEND_ORIGINS DATABASE_URL REDIS_URL IDENTITY_SERVICE_BASE_URL MESSENGER_SERVICE_BASE_URL JWT_VERIFYING_KEY CONTACT_POLICY_SYNC_SECRET; do
  require_key "$messenger_env" "$key" messenger
done

info "Checking production modes"
check_exact "$identity_env" APP_ENV production identity_service
check_exact "$messenger_env" APP_ENV production messenger
check_exact "$messenger_env" DJANGO_DEBUG False messenger

info "Checking production URL schemes"
check_starts_with "$identity_env" FRONTEND_ORIGINS https:// identity_service
check_starts_with "$identity_env" MESSENGER_SERVICE_BASE_URL https:// identity_service
check_starts_with "$messenger_env" FRONTEND_ORIGINS https:// messenger
check_starts_with "$messenger_env" DJANGO_CSRF_TRUSTED_ORIGINS https:// messenger
check_starts_with "$messenger_env" IDENTITY_SERVICE_BASE_URL https:// messenger
check_starts_with "$messenger_env" MESSENGER_SERVICE_BASE_URL https:// messenger

info "Checking production URLs do not contain local-only values"
for key in FRONTEND_ORIGINS MESSENGER_SERVICE_BASE_URL; do check_not_local "$identity_env" "$key" identity_service; done
for key in FRONTEND_ORIGINS DJANGO_CSRF_TRUSTED_ORIGINS IDENTITY_SERVICE_BASE_URL MESSENGER_SERVICE_BASE_URL REDIS_URL; do check_not_local "$messenger_env" "$key" messenger; done

info "Checking shared secrets without printing them"
if [[ "$use_examples" -eq 1 ]]; then
  warn "Skipping exact shared-secret comparison for example templates."
else
  compare_secret "$identity_env" JWT_SECRET_KEY identity_service "$messenger_env" JWT_VERIFYING_KEY messenger
  compare_secret "$identity_env" MESSENGER_INTERNAL_SECRET identity_service "$messenger_env" CONTACT_POLICY_SYNC_SECRET messenger
fi

placeholder_warnings "$identity_env" identity_service
placeholder_warnings "$messenger_env" messenger

info "Secret fingerprints only, safe to paste"
printf 'identity JWT_SECRET_KEY fingerprint              : %s\n' "$(secret_fingerprint "$(value_of "$identity_env" JWT_SECRET_KEY)")"
printf 'messenger JWT_VERIFYING_KEY fingerprint          : %s\n' "$(secret_fingerprint "$(value_of "$messenger_env" JWT_VERIFYING_KEY)")"
printf 'identity MESSENGER_INTERNAL_SECRET fingerprint   : %s\n' "$(secret_fingerprint "$(value_of "$identity_env" MESSENGER_INTERNAL_SECRET)")"
printf 'messenger CONTACT_POLICY_SYNC_SECRET fingerprint : %s\n' "$(secret_fingerprint "$(value_of "$messenger_env" CONTACT_POLICY_SYNC_SECRET)")"

if [[ "$has_failure" -ne 0 ]]; then
  die "Production env contract check FAILED."
fi

pass "Production env contract check PASSED"
