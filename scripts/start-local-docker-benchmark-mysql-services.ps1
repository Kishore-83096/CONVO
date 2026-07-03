param(
    [string]$Root = "D:\VENV\PARROT-V2"
)

$ErrorActionPreference = "Stop"

$networkName = "myna-local"

$mysqlContainer = "mysql-benchmark-local"
$redisContainer = "redis"
$identityContainer = "identity-service-local"
$messengerContainer = "messenger-service-local"

$identityImage = "identity-service-local:dev"
$messengerImage = "messenger-service-local:dev"

$identityEnv = "identity_service\.env.benchmark.mysql-docker.local"
$messengerEnv = "messenger\.env.benchmark.mysql-docker.local"

function Assert-LastCommandOk {
    param([string]$StepName)

    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE"
    }
}

function Wait-HttpOk {
    param(
        [string]$Name,
        [string]$Url,
        [int]$MaxAttempts = 60
    )

    Write-Host "Waiting for ${Name}: $Url" -ForegroundColor Cyan

    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5
            Write-Host "$Name is ready." -ForegroundColor Green
            return
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    throw "$Name did not become ready at $Url"
}

function Wait-MySqlReady {
    param(
        [string]$ContainerName,
        [string]$RootPassword
    )

    Write-Host "Waiting for MySQL container: $ContainerName" -ForegroundColor Cyan

    for ($i = 1; $i -le 60; $i++) {
        docker exec -e MYSQL_PWD=$RootPassword $ContainerName mysqladmin ping -h 127.0.0.1 -uroot --silent 2>$null

        if ($LASTEXITCODE -eq 0) {
            Write-Host "MySQL is ready." -ForegroundColor Green
            return
        }

        Start-Sleep -Seconds 2
    }

    docker logs $ContainerName --tail 100
    throw "MySQL did not become ready."
}

Set-Location $Root

Write-Host ""
Write-Host "Starting Docker-MySQL benchmark services..." -ForegroundColor Cyan

foreach ($requiredPath in @($identityEnv, $messengerEnv)) {
    if (-not (Test-Path $requiredPath)) {
        throw "Missing env file: $requiredPath"
    }
}

$networkExists = docker network ls --format "{{.Name}}" | Where-Object { $_ -eq $networkName }

if ($networkExists -ne $networkName) {
    docker network create $networkName | Out-Null
    Write-Host "Created Docker network: $networkName" -ForegroundColor Green
} else {
    Write-Host "Docker network already exists: $networkName" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Checking benchmark MySQL container..." -ForegroundColor Cyan

$mysqlRunning = docker ps --filter "name=^$mysqlContainer$" --format "{{.Names}}"

if ($mysqlRunning -ne $mysqlContainer) {
    throw "MySQL benchmark container is not running: $mysqlContainer. Start it first."
}

Wait-MySqlReady -ContainerName $mysqlContainer -RootPassword "myna_root_password"

Write-Host ""
Write-Host "Ensuring Redis is running..." -ForegroundColor Cyan

$redisRunning = docker ps --filter "name=^$redisContainer$" --format "{{.Names}}"

if ($redisRunning -ne $redisContainer) {
    $oldRedis = docker ps -a --filter "name=^$redisContainer$" --format "{{.Names}}"

    if ($oldRedis -eq $redisContainer) {
        docker rm -f $redisContainer | Out-Null
    }

    docker run -d `
        --name $redisContainer `
        --network $networkName `
        -p 6379:6379 `
        redis:7-alpine | Out-Null

    Assert-LastCommandOk "Start Redis"
    Write-Host "Started Redis container." -ForegroundColor Green
} else {
    Write-Host "Redis already running." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Stopping old Identity and Messenger containers..." -ForegroundColor Cyan

foreach ($container in @($identityContainer, $messengerContainer)) {
    $old = docker ps -a --filter "name=^$container$" --format "{{.Names}}"

    if ($old -eq $container) {
        docker rm -f $container | Out-Null
        Write-Host "Removed old container: $container" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Building Identity image..." -ForegroundColor Cyan

docker build `
    -t $identityImage `
    ".\identity_service"

Assert-LastCommandOk "Build Identity image"

Write-Host ""
Write-Host "Building Messenger image..." -ForegroundColor Cyan

docker build `
    -t $messengerImage `
    ".\messenger"

Assert-LastCommandOk "Build Messenger image"

Write-Host ""
Write-Host "Starting Identity with Docker MySQL env..." -ForegroundColor Cyan

docker run -d `
    --name $identityContainer `
    --network $networkName `
    --env-file ".\$identityEnv" `
    -p 5000:5000 `
    $identityImage | Out-Null

Assert-LastCommandOk "Start Identity container"

Write-Host ""
Write-Host "Starting Messenger with Docker MySQL env..." -ForegroundColor Cyan

docker run -d `
    --name $messengerContainer `
    --network $networkName `
    --env-file ".\$messengerEnv" `
    -p 8000:8000 `
    $messengerImage | Out-Null

Assert-LastCommandOk "Start Messenger container"

Write-Host ""
Write-Host "Waiting for services to pass health checks..." -ForegroundColor Cyan

try {
    Wait-HttpOk -Name "Identity" -Url "http://127.0.0.1:5000/api/v1/health/"
    Wait-HttpOk -Name "Messenger" -Url "http://127.0.0.1:8000/api/v1/health/"
} catch {
    Write-Host ""
    Write-Host "Identity logs:" -ForegroundColor Red
    docker logs $identityContainer --tail 120

    Write-Host ""
    Write-Host "Messenger logs:" -ForegroundColor Red
    docker logs $messengerContainer --tail 120

    throw
}

Write-Host ""
Write-Host "Docker-MySQL benchmark services are ready." -ForegroundColor Green

Write-Host ""
Write-Host "Running containers:" -ForegroundColor Cyan
docker ps --filter "name=identity-service-local" --filter "name=messenger-service-local" --filter "name=mysql-benchmark-local" --filter "name=redis" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Write-Host ""
Write-Host "Expected internal DB paths:" -ForegroundColor Cyan
Write-Host "  Identity  -> mysql-benchmark-local:3306/myna_identity_benchmark" -ForegroundColor Green
Write-Host "  Messenger -> mysql-benchmark-local:3306/myna_messenger_benchmark" -ForegroundColor Green
Write-Host "  Redis     -> redis:6379" -ForegroundColor Green

