param(
    [switch]$Volumes
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

if ($Volumes) {
    docker compose down -v
} else {
    docker compose down
}
