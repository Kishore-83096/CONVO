#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_base_files
require_gcloud
require_docker

tag="${1:-$(gcp_tag)}"
project="$(gcp_project)"
region="$(gcp_region)"
repo="$(gcp_repo)"
registry_host="${region}-docker.pkg.dev"
identity_image="$(identity_image_url "$tag")"
messenger_image="$(messenger_image_url "$tag")"

info "Ensuring Artifact Registry repository exists"
gcloud services enable artifactregistry.googleapis.com --project "$project" --quiet
if ! gcloud artifacts repositories describe "$repo" --location "$region" --project "$project" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$repo" --repository-format=docker --location "$region" --project "$project" --description="Myna application images"
fi

gcloud auth configure-docker "$registry_host" --quiet

info "Building canonical Identity image"
docker build -t "$identity_image" -f identity_service/Dockerfile identity_service
info "Building canonical Messenger image"
docker build -t "$messenger_image" -f messenger/Dockerfile messenger

info "Pushing Identity image"
docker push "$identity_image"
info "Pushing Messenger image"
docker push "$messenger_image"

printf '\nIdentity image:  %s\nMessenger image: %s\n' "$identity_image" "$messenger_image"
