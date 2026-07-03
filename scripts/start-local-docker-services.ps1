$ErrorActionPreference = "Stop"

$root = "D:\VENV\PARROT-V2"
$networkName = "myna-local"
$identityImage = "identity-service-local:dev"
$messengerImage = "messenger-service-local:dev"
$identityContainer = "identity-service-local"
$messengerContainer = "messenger-service-local"
$redisContainer = "redis"
$identityEnvFile = "identity_service\.env.docker.local"
$messengerEnvFile = "messenger\.env.docker.local"

Set-Location $root

Write-Host ""
Write-Host "Starting Myna local Docker services..." -ForegroundColor Cyan

if (-not (Test-Path $identityEnvFile)) {
    throw "Missing env file: $identityEnvFile"
}

if (-not (Test-Path $messengerEnvFile)) {
    throw "Missing env file: $messengerEnvFile"
}

$networkExists = docker network ls --format "{{.Name}}" | Where-Object { $_ -eq $networkName }

if ($networkExists -ne $networkName) {
    docker network create $networkName | Out-Null
    Write-Host "Created Docker network: $networkName" -ForegroundColor Green
} else {
    Write-Host "Docker network exists: $networkName" -ForegroundColor Green
}

foreach ($container in @($messengerContainer, $identityContainer, $redisContainer)) {
    $exists = docker ps -a --filter "name=^$container$" --format "{{.Names}}"
    if ($exists -eq $container) {
        docker rm -f $container | Out-Null
        Write-Host "Removed old container: $container" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Starting Redis..." -ForegroundColor Cyan
docker run -d --name $redisContainer --network $networkName -p 6379:6379 redis:7-alpine | Out-Null

Write-Host ""
Write-Host "Building Identity image..." -ForegroundColor Cyan
docker build -t $identityImage ".\identity_service"

Write-Host ""
Write-Host "Starting Identity..." -ForegroundColor Cyan
docker run -d --name $identityContainer --network $networkName --env-file $identityEnvFile -p 5000:5000 $identityImage | Out-Null

Write-Host "Waiting for Identity..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

$identityOk = $false
for ($i = 1; $i -le 15; $i++) {
    try {
        Invoke-RestMethod "http://127.0.0.1:5000/api/v1/health/" -TimeoutSec 5 | Out-Null
        $identityOk = $true
        Write-Host "Identity health OK." -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $identityOk) {
    docker logs --tail 200 $identityContainer
    throw "Identity failed health check."
}

Write-Host ""
Write-Host "Building Messenger image..." -ForegroundColor Cyan
docker build -t $messengerImage ".\messenger"

Write-Host ""
Write-Host "Starting Messenger..." -ForegroundColor Cyan
docker run -d --name $messengerContainer --network $networkName --env-file $messengerEnvFile -p 8000:8000 $messengerImage | Out-Null

Write-Host "Waiting for Messenger..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

$messengerOk = $false
for ($i = 1; $i -le 15; $i++) {
    try {
        Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health/" -TimeoutSec 5 | Out-Null
        $messengerOk = $true
        Write-Host "Messenger health OK." -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $messengerOk) {
    docker logs --tail 250 $messengerContainer
    throw "Messenger failed health check."
}

Write-Host ""
Write-Host "Container status:" -ForegroundColor Cyan
docker ps --filter "name=identity-service-local" --filter "name=messenger-service-local" --filter "name=redis" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Write-Host ""
Write-Host "Myna local Docker services started successfully." -ForegroundColor Green

