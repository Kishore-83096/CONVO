$ErrorActionPreference = "Stop"

$containers = @(
    "messenger-service-local",
    "identity-service-local",
    "redis"
)

Write-Host ""
Write-Host "Stopping local Docker services..." -ForegroundColor Cyan

foreach ($container in $containers) {
    $exists = docker ps -a --filter "name=^$container$" --format "{{.Names}}"

    if ($exists -eq $container) {
        Write-Host "Removing container: $container" -ForegroundColor Yellow
        docker rm -f $container | Out-Null
        Write-Host "Removed: $container" -ForegroundColor Green
    } else {
        Write-Host "Not found, skipped: $container" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "Local Docker services stopped." -ForegroundColor Green

Write-Host ""
Write-Host "Remaining Myna containers:" -ForegroundColor Cyan
docker ps -a --filter "name=identity-service-local" --filter "name=messenger-service-local" --filter "name=redis" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

