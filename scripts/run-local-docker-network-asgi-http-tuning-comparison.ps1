param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [string]$RunnerEnvFile = "messenger\.env.benchmark.runner.docker-network.local",
    [string]$IdentityEnvFile = "identity_service\env\identity.benchmark.env",
    [string]$MessengerEnvFile = "messenger\env\messenger.benchmark.env",
    [string]$ReportDir = "benchmark\myna_api_test_reports",
    [int]$DockerStatsIntervalMilliseconds = 1000,
    [switch]$StopOnRunFailure
)

$ErrorActionPreference = "Stop"

function New-SafeSlug {
    param([string]$Value)

    $slug = ($Value.ToLowerInvariant() -replace "[^a-z0-9]+", "_").Trim("_")
    if ([string]::IsNullOrWhiteSpace($slug)) {
        return "run"
    }
    return $slug
}

function Convert-EnvArrayToMap {
    param([string[]]$EnvAssignments)

    $map = [ordered]@{}
    foreach ($item in $EnvAssignments) {
        $text = ([string]$item).Trim()
        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }
        $equalIndex = $text.IndexOf("=")
        if ($equalIndex -lt 1) {
            continue
        }
        $map[$text.Substring(0, $equalIndex)] = $text.Substring($equalIndex + 1)
    }
    return $map
}

function New-FailedRunMetadata {
    param(
        [hashtable]$Config,
        [string[]]$MessengerEnv,
        [string[]]$RunnerEnv,
        [string]$ErrorMessage
    )

    return [ordered]@{
        run_label = $Config.Label
        benchmark_succeeded = $false
        benchmark_error = $ErrorMessage
        messenger_env = Convert-EnvArrayToMap -EnvAssignments $MessengerEnv
        runner_env = Convert-EnvArrayToMap -EnvAssignments $RunnerEnv
        cleanup_success = $false
        completed_at = (Get-Date).ToString("o")
    }
}

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
$metadataDir = Join-Path $resolvedReportDir "asgi_http_tuning_comparison_$stamp"
New-Item -ItemType Directory -Path $metadataDir -Force | Out-Null

$commonRunnerEnv = @(
    "MYNA_BENCHMARK_LEVELS=1,5,10,20,30,40,50,60,70,80,90,100",
    "MYNA_DISTRIBUTED_PAIR_COUNT=100",
    "MYNA_WARMUP_ALL_PAIRS=true",
    "MYNA_CONNECTION_WARMUP_ENABLED=true",
    "MYNA_CONNECTION_WARMUP_CONCURRENCY=100",
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

$commonMessengerEnv = @(
    "MESSENGER_PROCESS_ROLE=http",
    "GUNICORN_TIMEOUT=60",
    "GUNICORN_GRACEFUL_TIMEOUT=30",
    "GUNICORN_KEEP_ALIVE=5",
    "GUNICORN_MAX_REQUESTS=1000",
    "GUNICORN_MAX_REQUESTS_JITTER=100"
)

$configs = @(
    @{ Id = "A"; Label = "ASGI HTTP baseline"; Web = "5"; AsgiThreads = "8"; Backlog = "4096" },
    @{ Id = "B"; Label = "ASGI HTTP more workers"; Web = "6"; AsgiThreads = "8"; Backlog = "4096" },
    @{ Id = "C"; Label = "ASGI HTTP high workers"; Web = "8"; AsgiThreads = "8"; Backlog = "4096" },
    @{ Id = "D"; Label = "ASGI HTTP more ASGI threads"; Web = "5"; AsgiThreads = "16"; Backlog = "4096" },
    @{ Id = "E"; Label = "ASGI HTTP bigger backlog"; Web = "5"; AsgiThreads = "16"; Backlog = "8192" }
)

$runMetadata = @()

foreach ($config in $configs) {
    $slug = New-SafeSlug -Value ("{0}_{1}" -f $config.Id, $config.Label)
    $testRunId = "myna-asgi-http-$($stamp -replace '[^0-9A-Za-z]', '')-$($config.Id.ToLowerInvariant())"
    $metadataPath = Join-Path $metadataDir "$slug.run.json"

    $messengerEnv = @(
        "WEB_CONCURRENCY=$($config.Web)",
        "ASGI_THREADS=$($config.AsgiThreads)",
        "GUNICORN_BACKLOG=$($config.Backlog)"
    )
    $messengerEnv += $commonMessengerEnv

    $runnerEnv = @(
        "MYNA_REPORT_FILE_PREFIX=myna_asgi_http_tuning_$slug",
        "MYNA_TEST_RUN_ID=$testRunId"
    )
    $runnerEnv += $commonRunnerEnv

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "Running $($config.Id). $($config.Label)" -ForegroundColor Cyan
    Write-Host "role=http WEB_CONCURRENCY=$($config.Web) ASGI_THREADS=$($config.AsgiThreads) GUNICORN_BACKLOG=$($config.Backlog)" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Cyan

    try {
        & ".\scripts\run-local-docker-network-benchmark-accurate-timing.ps1" `
            -Root $Root `
            -RunnerEnvFile $RunnerEnvFile `
            -IdentityEnvFile $IdentityEnvFile `
            -MessengerEnvFile $MessengerEnvFile `
            -ReportDir $ReportDir `
            -DockerStatsIntervalMilliseconds $DockerStatsIntervalMilliseconds `
            -MessengerEnv $messengerEnv `
            -RunnerEnv $runnerEnv `
            -RunLabel "$($config.Id). $($config.Label)" `
            -RunMetadataOutputPath $metadataPath
    }
    catch {
        $message = $_.Exception.Message
        Write-Host "Run failed: $message" -ForegroundColor Red
        if (-not (Test-Path $metadataPath)) {
            $failedMetadata = New-FailedRunMetadata -Config $config -MessengerEnv $messengerEnv -RunnerEnv $runnerEnv -ErrorMessage $message
            $failedMetadata | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $metadataPath
        }
        if ($StopOnRunFailure) {
            throw
        }
    }

    $item = Get-Content -Raw $metadataPath | ConvertFrom-Json
    $runMetadata += $item
}

$manifestPath = Join-Path $metadataDir "asgi_http_tuning_comparison_runs.json"
$manifest = [ordered]@{
    created_at = (Get-Date).ToString("o")
    report_type = "asgi_http_tuning_comparison"
    runs = $runMetadata
}
$manifest | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 $manifestPath

$combinedReportPath = Join-Path $resolvedReportDir "asgi_http_tuning_comparison_$stamp.md"
python ".\scripts\build-asgi-http-tuning-comparison-report.py" `
    --runs-manifest $manifestPath `
    --output-md $combinedReportPath

if ($LASTEXITCODE -ne 0) {
    throw "ASGI HTTP tuning comparison report generation failed."
}

Write-Host ""
Write-Host "ASGI HTTP tuning comparison complete." -ForegroundColor Green
Write-Host "  Combined report: $combinedReportPath" -ForegroundColor Green
Write-Host "  Run manifest:    $manifestPath" -ForegroundColor Green
