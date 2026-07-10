#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_repo_files

forbidden='MESSENGER_HTTP_REPLICAS|HTTP_REPLICAS|MESSENGER_INSTANCE_COUNT|REPLICA_COUNT'

if grep -R -n -E "$forbidden" \
  "$repo_root/messenger" \
  "$repo_root/compose.yml" \
  "$repo_root/.env.example" \
  --exclude='validate-no-local-replica-env.sh' 2>/dev/null; then
  fail "A local/application HTTP replica-count variable still exists in the runtime architecture"
fi

echo "Static check passed: Messenger/Compose configuration contains no HTTP replica-count variable."

if command -v gcloud >/dev/null 2>&1 && [[ -n "$(dotenv_get GCP_PROJECT_ID)" ]]; then
  service="$(value_or_default GCP_MESSENGER_SERVICE_NAME myna-messenger)"
  region="$(gcp_region)"
  project="$(gcp_project)"
  if gcloud run services describe "$service" --region "$region" --project "$project" --format=json >/tmp/myna-cloud-run-service.json 2>/dev/null; then
    python3 - /tmp/myna-cloud-run-service.json <<'PY'
import json, re, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
forbidden = re.compile(r"^(MESSENGER_HTTP_REPLICAS|HTTP_REPLICAS|MESSENGER_INSTANCE_COUNT|REPLICA_COUNT)$")
names = []
for container in (((obj.get("spec") or {}).get("template") or {}).get("spec") or {}).get("containers", []):
    names.extend(str(item.get("name", "")) for item in container.get("env", []))
bad = sorted(name for name in names if forbidden.match(name))
if bad:
    raise SystemExit("Cloud Run Messenger contains forbidden replica env vars: " + ", ".join(bad))
print("Cloud Run runtime check passed: no local HTTP replica-count environment variable is deployed.")
PY
    rm -f /tmp/myna-cloud-run-service.json
  else
    echo "Cloud Run Messenger service is not deployed yet; runtime env check skipped."
  fi
fi
