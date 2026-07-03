param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [string]$RunnerEnvFile = "messenger\.env.benchmark.runner.docker-network.local"
)

$ErrorActionPreference = "Stop"

$networkName = "myna-local"
$runnerContainer = "myna-benchmark-runner"
$precheckContainer = "myna-benchmark-runner-precheck"
$baseMessengerImage = "messenger-service-local:dev"
$benchmarkRunnerImage = "messenger-benchmark-runner-local:dev"

function Assert-LastCommandOk {
    param([string]$StepName)

    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE"
    }
}

Set-Location $Root

Write-Host ""
Write-Host "Running benchmark INSIDE Docker network..." -ForegroundColor Cyan

if (-not (Test-Path $RunnerEnvFile)) { throw "Missing runner env file: $RunnerEnvFile" }
if (-not (Test-Path "messenger\Dockerfile.benchmark-runner")) { throw "Missing messenger\Dockerfile.benchmark-runner" }
if (-not (Test-Path "messenger\requirements-benchmark.txt")) { throw "Missing messenger\requirements-benchmark.txt" }
if (-not (Test-Path "messenger\api_tests")) { throw "Missing messenger\api_tests folder on host." }

if (-not (Test-Path "benchmark")) {
    New-Item -ItemType Directory -Path "benchmark" -Force | Out-Null
}

$networkExists = docker network ls --format "{{.Name}}" | Where-Object { $_ -eq $networkName }
if ($networkExists -ne $networkName) {
    throw "Docker network not found: $networkName. Start benchmark services first."
}

foreach ($container in @("identity-service-local", "messenger-service-local", "redis")) {
    $running = docker ps --filter "name=^$container$" --format "{{.Names}}"
    if ($running -ne $container) {
        throw "Required container is not running: $container. Run start-local-docker-benchmark-services.ps1 first."
    }
    Write-Host "Container running: $container" -ForegroundColor Green
}

$baseImageExists = docker images --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -eq $baseMessengerImage }
if ($baseImageExists -ne $baseMessengerImage) {
    throw "Base Messenger image not found: $baseMessengerImage. Run start-local-docker-benchmark-services.ps1 first."
}

Write-Host ""
Write-Host "Building clean benchmark runner image..." -ForegroundColor Cyan

docker build `
    -t $benchmarkRunnerImage `
    -f ".\messenger\Dockerfile.benchmark-runner" `
    ".\messenger"

Assert-LastCommandOk "Benchmark runner image build"

foreach ($container in @($runnerContainer, $precheckContainer)) {
    $old = docker ps -a --filter "name=^$container$" --format "{{.Names}}"
    if ($old -eq $container) { docker rm -f $container | Out-Null }
}

$benchmarkPath = (Resolve-Path "benchmark").Path
$apiTestsPath = (Resolve-Path "messenger\api_tests").Path
$envPath = (Resolve-Path $RunnerEnvFile).Path

Write-Host ""
Write-Host "Testing Docker DNS from benchmark runner container..." -ForegroundColor Cyan

docker run --rm `
    --name $precheckContainer `
    --network $networkName `
    --env-file $envPath `
    -v "${benchmarkPath}:/reports" `
    $benchmarkRunnerImage `
    -c "import urllib.request; print(urllib.request.urlopen('http://identity-service-local:5000/api/v1/health/', timeout=10).read().decode()); print(urllib.request.urlopen('http://messenger-service-local:8000/api/v1/health/', timeout=10).read().decode())"

Assert-LastCommandOk "Docker DNS precheck"

Write-Host ""
Write-Host "Starting Docker-network benchmark runner..." -ForegroundColor Cyan
Write-Host "Actual URLs use Docker DNS:" -ForegroundColor Yellow
Write-Host "  http://identity-service-local:5000" -ForegroundColor Yellow
Write-Host "  http://messenger-service-local:8000" -ForegroundColor Yellow
Write-Host "Cleanup uses direct Django inside runner, not docker exec." -ForegroundColor Yellow

docker run --rm `
    --name $runnerContainer `
    --network $networkName `
    --env-file $envPath `
    -v "${benchmarkPath}:/reports" `
    -v "${apiTestsPath}:/app/api_tests:ro" `
    $benchmarkRunnerImage `
    /app/api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py

Assert-LastCommandOk "Docker-network benchmark"

Write-Host ""
Write-Host "Docker-network benchmark completed." -ForegroundColor Green

Write-Host ""
Write-Host "Latest reports:" -ForegroundColor Cyan
Get-ChildItem "benchmark\myna_api_test_reports" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 10 Name, LastWriteTime, Length
