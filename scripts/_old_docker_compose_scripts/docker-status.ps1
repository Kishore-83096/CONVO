$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

docker compose ps
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
