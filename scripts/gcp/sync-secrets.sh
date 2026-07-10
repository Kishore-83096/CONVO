#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_base_files
require_gcloud

project="$(gcp_project)"
sa_name="$(runtime_service_account_name)"
sa_email="$(runtime_service_account_email)"

info "Enabling the GCP APIs used by the Myna deployment"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iam.googleapis.com --project "$project" --quiet

if ! gcloud iam service-accounts describe "$sa_email" --project "$project" >/dev/null 2>&1; then
  info "Creating runtime service account: $sa_email"
  gcloud iam service-accounts create "$sa_name" --display-name="Myna Cloud Run runtime" --project "$project"
fi

gcloud projects add-iam-policy-binding "$project" \
  --member="serviceAccount:$sa_email" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None \
  --quiet >/dev/null

put_secret() {
  local suffix="$1" value="$2" name
  name="$(secret_name "$suffix")"
  [[ -n "$value" && "$value" != "change-me" ]] || fail "Secret source for $name is empty or still change-me"
  if ! gcloud secrets describe "$name" --project "$project" >/dev/null 2>&1; then
    gcloud secrets create "$name" --replication-policy=automatic --project "$project" --quiet >/dev/null
  fi
  printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- --project "$project" --quiet >/dev/null
  echo "Updated secret: $name"
}

cloudinary_url="$(dotenv_get GCP_CLOUDINARY_URL)"
[[ -n "$cloudinary_url" ]] || cloudinary_url="$(dotenv_get CLOUDINARY_URL)"
[[ "$cloudinary_url" == cloudinary://* ]] || fail "GCP_CLOUDINARY_URL/CLOUDINARY_URL must be a cloudinary:// URL"
case "$cloudinary_url" in
  *API_KEY*|*API_SECRET*|*CLOUD_NAME*|*change-me*)
    fail "Replace the Cloudinary placeholder before synchronizing GCP secrets"
    ;;
esac

put_secret identity-secret-key "$(require_dotenv_value SECRET_KEY)"
put_secret jwt-secret-key "$(require_dotenv_value JWT_SECRET_KEY)"
put_secret messenger-internal-secret "$(require_dotenv_value MESSENGER_INTERNAL_SECRET)"
put_secret django-secret-key "$(require_dotenv_value DJANGO_SECRET_KEY)"
put_secret cloudinary-url "$cloudinary_url"
put_secret identity-database-url "$(require_dotenv_value GCP_IDENTITY_DATABASE_URL)"
put_secret messenger-database-url "$(require_dotenv_value GCP_MESSENGER_DATABASE_URL)"
put_secret redis-url "$(require_dotenv_value GCP_REDIS_URL)"
put_secret cache-redis-url "$(require_dotenv_value GCP_CACHE_REDIS_URL)"

info "Secret Manager synchronization complete. Secret values were not printed."
