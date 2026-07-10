#!/usr/bin/env bash
set -euo pipefail

_gcp_common_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$_gcp_common_dir/../.." && pwd)"
env_file="$repo_root/.env"

fail() {
  echo "ERROR: $*" >&2
  exit 2
}

info() {
  echo "==> $*"
}

dotenv_get() {
  local key="$1"
  python3 - "$env_file" "$key" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
key = sys.argv[2]
for raw in path.read_text(encoding="utf-8-sig").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    current, value = line.split("=", 1)
    if current.strip() != key:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    print(value)
    break
PY
}

value_or_default() {
  local key="$1" default="$2" value
  value="$(dotenv_get "$key")"
  printf '%s' "${value:-$default}"
}

require_dotenv_value() {
  local key="$1" value
  value="$(dotenv_get "$key")"
  [[ -n "$value" && "$value" != "change-me" ]] || fail "$key must be set in .env"
  printf '%s' "$value"
}

require_repo_files() {
  [[ -f "$repo_root/compose.yml" ]] || fail "Missing $repo_root/compose.yml"
  [[ -f "$repo_root/.env.example" ]] || fail "Missing $repo_root/.env.example"
}

require_base_files() {
  require_repo_files
  [[ -f "$env_file" ]] || fail "Missing $env_file. Create it from .env.example or run ./scripts/migrate-env-to-root.sh"
}

require_gcloud() {
  command -v gcloud >/dev/null 2>&1 || fail "gcloud CLI is required"
  gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || fail "No active gcloud account. Run: gcloud auth login"
}

require_docker() {
  command -v docker >/dev/null 2>&1 || fail "Docker CLI is required"
  docker info >/dev/null 2>&1 || fail "Docker daemon is not available"
}

gcp_project() { require_dotenv_value GCP_PROJECT_ID; }
gcp_region() { value_or_default GCP_REGION asia-south1; }
gcp_repo() { value_or_default GCP_ARTIFACT_REGISTRY_REPOSITORY myna; }
gcp_tag() { value_or_default GCP_IMAGE_TAG latest; }
secret_prefix() { value_or_default GCP_SECRET_PREFIX myna; }
runtime_service_account_name() { value_or_default GCP_RUNTIME_SERVICE_ACCOUNT_NAME myna-runtime; }
runtime_service_account_email() { printf '%s@%s.iam.gserviceaccount.com' "$(runtime_service_account_name)" "$(gcp_project)"; }

identity_image_url() {
  printf '%s-docker.pkg.dev/%s/%s/myna-identity:%s' "$(gcp_region)" "$(gcp_project)" "$(gcp_repo)" "${1:-$(gcp_tag)}"
}

messenger_image_url() {
  printf '%s-docker.pkg.dev/%s/%s/myna-messenger:%s' "$(gcp_region)" "$(gcp_project)" "$(gcp_repo)" "${1:-$(gcp_tag)}"
}

secret_name() {
  printf '%s-%s' "$(secret_prefix)" "$1"
}

network_flags() {
  local network subnet
  network="$(dotenv_get GCP_VPC_NETWORK)"
  subnet="$(dotenv_get GCP_VPC_SUBNET)"
  if [[ -n "$network" || -n "$subnet" ]]; then
    [[ -n "$network" && -n "$subnet" ]] || fail "GCP_VPC_NETWORK and GCP_VPC_SUBNET must either both be set or both be empty"
    printf '%s\0%s\0%s\0%s\0' --network "$network" --subnet "$subnet"
  fi
}
