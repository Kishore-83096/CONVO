#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

identity_base_url=""
messenger_base_url=""
confirm=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --identity-base-url) identity_base_url="${2%/}"; shift 2 ;;
    --messenger-base-url) messenger_base_url="${2%/}"; shift 2 ;;
    --confirm-production-smoke) confirm=1; shift ;;
    -h|--help) printf 'Usage: %s --identity-base-url URL --messenger-base-url URL --confirm-production-smoke\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

assert_production_url() {
  local name="$1" url="$2" bad
  [[ -n "$url" ]] || die "$name is empty"
  [[ "$url" == https://* ]] || die "$name must start with https:// for production"
  for bad in 127.0.0.1 localhost host.docker.internal identity-service-local messenger-service-local your- replace- example.com; do
    [[ "$url" != *"$bad"* ]] || die "$name contains placeholder/local value: $url"
  done
}

if [[ "$confirm" -ne 1 ]]; then
  warn "Production smoke test was NOT started."
  warn "This script creates temporary users on your production services and then deletes them."
  warn "Run again with --confirm-production-smoke when you are ready."
  exit 1
fi

assert_production_url IdentityBaseUrl "$identity_base_url"
assert_production_url MessengerBaseUrl "$messenger_base_url"

info "Running production smoke test"
printf 'Identity : %s\nMessenger: %s\n' "$identity_base_url" "$messenger_base_url"
"$repo_root/scripts/smoke-local-python-contract.sh" --identity-base-url "$identity_base_url" --messenger-base-url "$messenger_base_url"
pass "Production smoke test completed"
