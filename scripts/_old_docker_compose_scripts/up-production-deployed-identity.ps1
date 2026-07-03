$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

& (Join-Path $PSScriptRoot "init-env.ps1")
docker compose --profile production-deployed-identity up -d --build

Write-Host ""
Write-Host "Messenger: http://127.0.0.1:8000"
Write-Host "Health:"
Write-Host "  Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/"
Write-Host ""
Write-Host "Ensure JWT_VERIFYING_KEY matches the deployed Identity JWT secret or public key."
Write-Host "Ensure CONTACT_POLICY_SYNC_SECRET matches the deployed Identity MESSENGER_INTERNAL_SECRET."
