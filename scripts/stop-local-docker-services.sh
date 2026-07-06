#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

info "Stopping local Docker services"
for container in messenger-service-local identity-service-local redis; do
  if container_exists "$container"; then
    warn "Removing container: $container"
    docker rm -f "$container" >/dev/null
    pass "Removed: $container"
  else
    warn "Not found, skipped: $container"
  fi
done

pass "Local Docker services stopped"
info "Remaining Myna containers"
docker ps -a --filter "name=identity-service-local" --filter "name=messenger-service-local" --filter "name=redis" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
