param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [string]$RunnerEnvFile = "messenger\.env.benchmark.runner.docker-network.local",
    [string]$IdentityEnvFile = "identity_service\env\identity.benchmark.env",
    [string]$MessengerEnvFile = "messenger\env\messenger.benchmark.env",
    [string]$ReportDir = "benchmark\myna_api_test_reports",
    [string]$MessengerHttpServerMode = "asgi",
    [string]$WebConcurrency = "5",
    [string]$AsgiThreads = "8",
    [string]$GunicornThreads = "",
    [int]$DockerStatsIntervalMilliseconds = 1000
)

$ErrorActionPreference = "Stop"

Set-Location $Root

if (-not (Test-Path $IdentityEnvFile) -and (Test-Path "identity_service\.env.benchmark.mysql-docker.local")) {
    $IdentityEnvFile = "identity_service\.env.benchmark.mysql-docker.local"
}
if (-not (Test-Path $MessengerEnvFile) -and (Test-Path "messenger\.env.benchmark.mysql-docker.local")) {
    $MessengerEnvFile = "messenger\.env.benchmark.mysql-docker.local"
}

$resolvedReportDir = Join-Path $Root $ReportDir
if (-not (Test-Path $resolvedReportDir)) {
    New-Item -ItemType Directory -Path $resolvedReportDir -Force | Out-Null
}

$stamp = Get-Date -Format "HH-mm-ss_yyyy-MM-dd"
$metadataPath = Join-Path $resolvedReportDir "endpoint_gap_comparison_$stamp.run.json"
$endpointReportPath = Join-Path $resolvedReportDir "endpoint_gap_comparison_$stamp.md"
$testRunId = "myna-endpoint-$($stamp -replace '[^0-9A-Za-z]', '')"

$messengerEnv = @(
    "MESSENGER_PROCESS_ROLE=http",
    "MESSENGER_HTTP_SERVER_MODE=$MessengerHttpServerMode",
    "WEB_CONCURRENCY=$WebConcurrency",
    "GUNICORN_BACKLOG=4096",
    "GUNICORN_TIMEOUT=60",
    "GUNICORN_GRACEFUL_TIMEOUT=30",
    "GUNICORN_KEEP_ALIVE=5"
)
if ($MessengerHttpServerMode -eq "asgi" -and -not [string]::IsNullOrWhiteSpace($AsgiThreads)) {
    $messengerEnv += "ASGI_THREADS=$AsgiThreads"
}
if ($MessengerHttpServerMode -eq "wsgi") {
    $threads = if ([string]::IsNullOrWhiteSpace($GunicornThreads)) { "8" } else { $GunicornThreads }
    $messengerEnv += "GUNICORN_THREADS=$threads"
}

$runnerEnv = @(
    "MYNA_REPORT_FILE_PREFIX=myna_endpoint_gap_comparison",
    "MYNA_TEST_RUN_ID=$testRunId",
    "MYNA_ENDPOINT_BENCHMARK_LEVELS=1,5,10,20,30,40,50,60,70,80,90,100",
    "MYNA_ENDPOINT_BENCHMARK_REQUESTS_PER_LEVEL=100",
    "MYNA_DISTRIBUTED_PAIR_COUNT=100",
    "MYNA_WARMUP_ALL_PAIRS=true",
    "MYNA_HTTP_MAX_CONNECTIONS=300",
    "MYNA_HTTP_MAX_KEEPALIVE_CONNECTIONS=300",
    "MYNA_HTTP_KEEPALIVE_EXPIRY_SECONDS=60",
    "MYNA_HTTP_POOL_TIMEOUT_SECONDS=10",
    "MYNA_BENCHMARK_COOLDOWN_SECONDS=3",
    "MYNA_REQUEST_TIMEOUT_SECONDS=30",
    "MYNA_STOP_ON_FIRST_FAILED_LEVEL=false",
    "MYNA_CLEANUP_MESSENGER_DJANGO=true",
    "MYNA_CLEANUP_IDENTITY_USERS=true",
    "MYNA_RUNNER_PATH=docker-network"
)

Write-Host ""
Write-Host "Starting Docker-network endpoint gap comparison..." -ForegroundColor Cyan
Write-Host "mode=$MessengerHttpServerMode WEB_CONCURRENCY=$WebConcurrency ASGI_THREADS=$AsgiThreads GUNICORN_THREADS=$GunicornThreads" -ForegroundColor Yellow

$runError = $null
try {
    & ".\scripts\run-local-docker-network-benchmark-accurate-timing.ps1" `
        -Root $Root `
        -RunnerEnvFile $RunnerEnvFile `
        -IdentityEnvFile $IdentityEnvFile `
        -MessengerEnvFile $MessengerEnvFile `
        -ReportDir $ReportDir `
        -DockerStatsIntervalMilliseconds $DockerStatsIntervalMilliseconds `
        -BenchmarkScript "/app/api_tests/full_api_flow/myna_endpoint_gap_comparison_benchmark.py" `
        -MessengerEnv $messengerEnv `
        -RunnerEnv $runnerEnv `
        -RunLabel "Endpoint gap comparison" `
        -RunMetadataOutputPath $metadataPath
}
catch {
    $runError = $_.Exception.Message
    Write-Host "Endpoint benchmark wrapper reported: $runError" -ForegroundColor Yellow
}

if (-not (Test-Path $metadataPath)) {
    throw "Endpoint benchmark did not produce run metadata."
}

$metadata = Get-Content -Raw $metadataPath | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($metadata.json_report_path)) {
    throw "Endpoint benchmark did not produce a JSON report. Last error: $runError"
}

python ".\scripts\build-endpoint-gap-comparison-report.py" `
    --json-report $metadata.json_report_path `
    --output-md $endpointReportPath

if ($LASTEXITCODE -ne 0) {
    throw "Endpoint gap comparison report generation failed."
}

Write-Host ""
Write-Host "Endpoint gap comparison complete." -ForegroundColor Green
Write-Host "  JSON report:        $($metadata.json_report_path)" -ForegroundColor Green
Write-Host "  Gap analysis:       $($metadata.gap_report_path)" -ForegroundColor Green
Write-Host "  Endpoint report:    $endpointReportPath" -ForegroundColor Green
Write-Host "  Gunicorn log:       $($metadata.gunicorn_access_log_path)" -ForegroundColor Green
Write-Host "  Host Docker stats:  $($metadata.host_docker_stats_csv_path)" -ForegroundColor Green

if ($runError) {
    Write-Host ""
    Write-Host "Warning: the benchmark command reported an error after producing reports: $runError" -ForegroundColor Yellow
}
