#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_base_files
require_gcloud

tag="$(gcp_tag)"
skip_build=false
skip_secrets=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) tag="$2"; shift 2 ;;
    --skip-build) skip_build=true; shift ;;
    --skip-secret-sync) skip_secrets=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--tag TAG] [--skip-build] [--skip-secret-sync]"
      exit 0
      ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

project="$(gcp_project)"
region="$(gcp_region)"
sa_email="$(runtime_service_account_email)"
identity_service="$(value_or_default GCP_IDENTITY_SERVICE_NAME myna-identity)"
messenger_service="$(value_or_default GCP_MESSENGER_SERVICE_NAME myna-messenger)"
outbox_pool="$(value_or_default GCP_OUTBOX_WORKER_POOL_NAME myna-messenger-outbox)"
identity_job="$(value_or_default GCP_IDENTITY_MIGRATION_JOB_NAME myna-identity-migrate)"
messenger_job="$(value_or_default GCP_MESSENGER_MIGRATION_JOB_NAME myna-messenger-migrate)"
identity_image="$(identity_image_url "$tag")"
messenger_image="$(messenger_image_url "$tag")"

# Required production endpoints are secret sources. Validate before mutating Cloud Run.
frontend_origins="$(require_dotenv_value GCP_FRONTEND_ORIGINS)"
[[ "$frontend_origins" != *"your-frontend.example.com"* ]] || fail "Replace the GCP_FRONTEND_ORIGINS placeholder before deployment"
require_dotenv_value GCP_IDENTITY_DATABASE_URL >/dev/null
require_dotenv_value GCP_MESSENGER_DATABASE_URL >/dev/null
require_dotenv_value GCP_REDIS_URL >/dev/null
require_dotenv_value GCP_CACHE_REDIS_URL >/dev/null

"$repo_root/scripts/gcp/validate-no-local-replica-env.sh"
if [[ "$skip_build" != true ]]; then
  "$repo_root/scripts/gcp/build-and-push.sh" "$tag"
fi
if [[ "$skip_secrets" != true ]]; then
  "$repo_root/scripts/gcp/sync-secrets.sh"
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

mapfile -d '' -t vpc_flags < <(network_flags)

render_env() {
  python3 "$repo_root/scripts/gcp/render-env.py" --env-file "$env_file" "$@"
}

identity_secrets="SECRET_KEY=$(secret_name identity-secret-key):latest,JWT_SECRET_KEY=$(secret_name jwt-secret-key):latest,MESSENGER_INTERNAL_SECRET=$(secret_name messenger-internal-secret):latest,DATABASE_URL=$(secret_name identity-database-url):latest,CLOUDINARY_URL=$(secret_name cloudinary-url):latest"
messenger_secrets="DJANGO_SECRET_KEY=$(secret_name django-secret-key):latest,JWT_VERIFYING_KEY=$(secret_name jwt-secret-key):latest,CONTACT_POLICY_SYNC_SECRET=$(secret_name messenger-internal-secret):latest,DATABASE_URL=$(secret_name messenger-database-url):latest,REDIS_URL=$(secret_name redis-url):latest,CACHE_REDIS_URL=$(secret_name cache-redis-url):latest,CLOUDINARY_URL=$(secret_name cloudinary-url):latest"

identity_placeholder="https://pending.invalid"
messenger_placeholder="https://pending.invalid"
render_env --role identity-migrate --output "$tmpdir/identity-migrate.yaml" --messenger-url "$messenger_placeholder" --sync-required false
render_env --role messenger-migrate --output "$tmpdir/messenger-migrate.yaml" --identity-url "$identity_placeholder/api/v1" --messenger-url "$messenger_placeholder"

info "Deploying and executing controlled Identity migration job"
gcloud run jobs deploy "$identity_job" \
  --project "$project" --region "$region" --image "$identity_image" \
  --service-account "$sa_email" --tasks 1 --parallelism 1 --max-retries 1 --task-timeout 600s \
  --env-vars-file "$tmpdir/identity-migrate.yaml" --set-secrets "$identity_secrets" \
  --command python --args=-m,flask,--app,identity_service:app,db,upgrade \
  "${vpc_flags[@]}" --quiet
gcloud run jobs execute "$identity_job" --project "$project" --region "$region" --wait --quiet

info "Deploying and executing controlled Messenger migration job"
gcloud run jobs deploy "$messenger_job" \
  --project "$project" --region "$region" --image "$messenger_image" \
  --service-account "$sa_email" --tasks 1 --parallelism 1 --max-retries 1 --task-timeout 600s \
  --env-vars-file "$tmpdir/messenger-migrate.yaml" --set-secrets "$messenger_secrets" \
  --command python --args=manage.py,migrate,--noinput \
  "${vpc_flags[@]}" --quiet
gcloud run jobs execute "$messenger_job" --project "$project" --region "$region" --wait --quiet

render_env --role identity --output "$tmpdir/identity.yaml" --messenger-url "$messenger_placeholder" --sync-required false
info "Deploying Identity service with policy sync temporarily disabled until Messenger URL exists"
gcloud run deploy "$identity_service" \
  --project "$project" --region "$region" --image "$identity_image" --allow-unauthenticated \
  --service-account "$sa_email" \
  --min "$(value_or_default GCP_IDENTITY_MIN_INSTANCES 0)" \
  --max "$(value_or_default GCP_IDENTITY_MAX_INSTANCES 5)" \
  --concurrency "$(value_or_default GCP_IDENTITY_CONTAINER_CONCURRENCY 40)" \
  --cpu "$(value_or_default GCP_IDENTITY_CPU 1)" \
  --memory "$(value_or_default GCP_IDENTITY_MEMORY 512Mi)" \
  --timeout "$(value_or_default GCP_IDENTITY_TIMEOUT 60)s" \
  --env-vars-file "$tmpdir/identity.yaml" --set-secrets "$identity_secrets" \
  "${vpc_flags[@]}" --quiet
identity_url="$(gcloud run services describe "$identity_service" --project "$project" --region "$region" --format='value(status.url)')"
[[ -n "$identity_url" ]] || fail "Could not resolve Identity Cloud Run URL"

render_env --role messenger --output "$tmpdir/messenger.yaml" --identity-url "$identity_url/api/v1" --messenger-url "$messenger_placeholder"
info "Deploying Messenger HTTP Cloud Run service"
gcloud run deploy "$messenger_service" \
  --project "$project" --region "$region" --image "$messenger_image" --allow-unauthenticated \
  --service-account "$sa_email" \
  --min "$(value_or_default GCP_MESSENGER_MIN_INSTANCES 1)" \
  --max "$(value_or_default GCP_MESSENGER_MAX_INSTANCES 10)" \
  --concurrency "$(value_or_default GCP_MESSENGER_CONTAINER_CONCURRENCY 80)" \
  --cpu "$(value_or_default GCP_MESSENGER_CPU 1)" \
  --memory "$(value_or_default GCP_MESSENGER_MEMORY 1Gi)" \
  --timeout "$(value_or_default GCP_MESSENGER_TIMEOUT 60)s" \
  --env-vars-file "$tmpdir/messenger.yaml" --set-secrets "$messenger_secrets" \
  "${vpc_flags[@]}" --quiet
messenger_url="$(gcloud run services describe "$messenger_service" --project "$project" --region "$region" --format='value(status.url)')"
[[ -n "$messenger_url" ]] || fail "Could not resolve Messenger Cloud Run URL"

# Reconcile self/service URLs now that Cloud Run has assigned stable service URLs.
render_env --role messenger --output "$tmpdir/messenger.yaml" --identity-url "$identity_url/api/v1" --messenger-url "$messenger_url"
gcloud run deploy "$messenger_service" \
  --project "$project" --region "$region" --image "$messenger_image" --allow-unauthenticated \
  --service-account "$sa_email" \
  --min "$(value_or_default GCP_MESSENGER_MIN_INSTANCES 1)" \
  --max "$(value_or_default GCP_MESSENGER_MAX_INSTANCES 10)" \
  --concurrency "$(value_or_default GCP_MESSENGER_CONTAINER_CONCURRENCY 80)" \
  --cpu "$(value_or_default GCP_MESSENGER_CPU 1)" \
  --memory "$(value_or_default GCP_MESSENGER_MEMORY 1Gi)" \
  --timeout "$(value_or_default GCP_MESSENGER_TIMEOUT 60)s" \
  --env-vars-file "$tmpdir/messenger.yaml" --set-secrets "$messenger_secrets" \
  "${vpc_flags[@]}" --quiet

sync_required="$(value_or_default MESSENGER_POLICY_SYNC_REQUIRED true)"
render_env --role identity --output "$tmpdir/identity.yaml" --messenger-url "$messenger_url" --sync-required "$sync_required"
gcloud run deploy "$identity_service" \
  --project "$project" --region "$region" --image "$identity_image" --allow-unauthenticated \
  --service-account "$sa_email" \
  --min "$(value_or_default GCP_IDENTITY_MIN_INSTANCES 0)" \
  --max "$(value_or_default GCP_IDENTITY_MAX_INSTANCES 5)" \
  --concurrency "$(value_or_default GCP_IDENTITY_CONTAINER_CONCURRENCY 40)" \
  --cpu "$(value_or_default GCP_IDENTITY_CPU 1)" \
  --memory "$(value_or_default GCP_IDENTITY_MEMORY 512Mi)" \
  --timeout "$(value_or_default GCP_IDENTITY_TIMEOUT 60)s" \
  --env-vars-file "$tmpdir/identity.yaml" --set-secrets "$identity_secrets" \
  "${vpc_flags[@]}" --quiet

render_env --role outbox --output "$tmpdir/outbox.yaml" --identity-url "$identity_url/api/v1" --messenger-url "$messenger_url"
info "Deploying Messenger outbox role as a Cloud Run worker pool from the same Messenger image"
gcloud run worker-pools deploy "$outbox_pool" \
  --project "$project" --region "$region" --image "$messenger_image" \
  --service-account "$sa_email" \
  --instances "$(value_or_default GCP_OUTBOX_INSTANCES 1)" \
  --cpu "$(value_or_default GCP_OUTBOX_CPU 1)" \
  --memory "$(value_or_default GCP_OUTBOX_MEMORY 512Mi)" \
  --env-vars-file "$tmpdir/outbox.yaml" --update-secrets "$messenger_secrets" \
  "${vpc_flags[@]}" --quiet

"$repo_root/scripts/gcp/validate-no-local-replica-env.sh"

printf '\nGCP deployment complete.\nIdentity:  %s\nMessenger: %s\nOutbox worker pool: %s\n' "$identity_url" "$messenger_url" "$outbox_pool"
