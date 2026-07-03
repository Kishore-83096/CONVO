$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

& (Join-Path $PSScriptRoot "init-env.ps1")
docker compose --profile benchmark up -d --build

Write-Host ""
Write-Host "Benchmark Identity:  http://127.0.0.1:5000"
Write-Host "Benchmark Messenger: http://127.0.0.1:8000"
Write-Host "Health:"
Write-Host "  Invoke-RestMethod http://127.0.0.1:5000/api/v1/health"
Write-Host "  Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/"
Write-Host ""
docker compose ps
