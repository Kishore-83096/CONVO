param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [string]$RunnerEnvFile = "messenger\.env.benchmark.runner.docker-network.local",
    [string]$IdentityEnvFile = "identity_service\env\identity.benchmark.env",
    [string]$MessengerEnvFile = "messenger\env\messenger.benchmark.env",
    [string]$ReportDir = "benchmark\myna_api_test_reports",
    [int]$DockerStatsIntervalMilliseconds = 1000,
    [string]$BenchmarkScript = "/app/api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py",
    [string[]]$MessengerEnv = @(),
    [string[]]$RunnerEnv = @(),
    [string]$RunLabel = "",
    [string]$RunMetadataOutputPath = "",
    [string]$BenchmarkMySqlRootPassword = "benchmark_root_password",
    [string]$BenchmarkMySqlUser = "myna_benchmark",
    [string]$BenchmarkMySqlPassword = "myna_benchmark_password"
)

$ErrorActionPreference = "Stop"

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
            Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5 | Out-Null
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

function Repair-BenchmarkMySqlGrants {
    param(
        [string]$ContainerName,
        [string]$RootPassword,
        [string]$BenchmarkUser,
        [string]$BenchmarkPassword
    )

    Write-Host "Repairing benchmark MySQL user grants..." -ForegroundColor Cyan

    $grantSql = @"
CREATE DATABASE IF NOT EXISTS myna_identity_benchmark CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS myna_messenger_benchmark CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$BenchmarkUser'@'%' IDENTIFIED BY '$BenchmarkPassword';
ALTER USER '$BenchmarkUser'@'%' IDENTIFIED BY '$BenchmarkPassword';
GRANT ALL PRIVILEGES ON myna_identity_benchmark.* TO '$BenchmarkUser'@'%';
GRANT ALL PRIVILEGES ON myna_messenger_benchmark.* TO '$BenchmarkUser'@'%';
FLUSH PRIVILEGES;
SHOW GRANTS FOR '$BenchmarkUser'@'%';
"@

    $grantSql | docker exec -i -e MYSQL_PWD=$RootPassword $ContainerName mysql -uroot
    Assert-LastCommandOk "Repair benchmark MySQL grants"

    Write-Host "Benchmark MySQL grants are ready." -ForegroundColor Green
}

function Get-LatestBenchmarkJson {
    param([string]$Directory)

    return Get-ChildItem $Directory -Filter "*.json" -File |
        Where-Object {
            $_.Name -notlike "*cleanup*status*" -and
            $_.Name -notlike "*request_gap*"
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

function Get-DockerEnvArgs {
    param([string[]]$EnvAssignments)

    $args = @()
    foreach ($item in $EnvAssignments) {
        $trimmed = [string]$item
        $trimmed = $trimmed.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed)) {
            continue
        }
        if ($trimmed -notmatch "^[A-Za-z_][A-Za-z0-9_]*=") {
            throw "Invalid Docker env assignment: $trimmed"
        }
        $args += @("-e", $trimmed)
    }
    return $args
}

function Convert-EnvAssignmentsToMap {
    param([string[]]$EnvAssignments)

    $map = [ordered]@{}
    foreach ($item in $EnvAssignments) {
        $trimmed = [string]$item
        $trimmed = $trimmed.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed)) {
            continue
        }
        $equalIndex = $trimmed.IndexOf("=")
        if ($equalIndex -lt 1) {
            continue
        }
        $key = $trimmed.Substring(0, $equalIndex)
        $value = $trimmed.Substring($equalIndex + 1)
        $map[$key] = $value
    }
    return $map
}

Set-Location $Root

$networkName = "myna-local"
$mysqlContainer = "mysql-benchmark-local"
$redisContainer = "redis"
$identityContainer = "identity-service-local"
$messengerContainer = "messenger-service-local"
$identityImage = "identity-service-local:dev"
$messengerImage = "messenger-service-local:dev"
$benchmarkRunnerImage = "messenger-benchmark-runner-local:dev"
$runnerContainer = "myna-benchmark-runner"
$precheckContainer = "myna-benchmark-runner-precheck"
$gunicornLogContainer = "/tmp/myna_benchmark_gunicorn_access.log"
$gunicornAccessLogFormat = '%(t)s pid=%(p)s status=%(s)s duration_us=%(D)s method="%(m)s" path="%(U)s" run="%({x-myna-benchmark-run-id}i)s" req="%({x-myna-benchmark-request-id}i)s" phase="%({x-myna-benchmark-phase}i)s" concurrency="%({x-myna-benchmark-concurrency}i)s"'

if (-not (Test-Path $IdentityEnvFile) -and (Test-Path "identity_service\.env.benchmark.mysql-docker.local")) {
    $IdentityEnvFile = "identity_service\.env.benchmark.mysql-docker.local"
}
if (-not (Test-Path $MessengerEnvFile) -and (Test-Path "messenger\.env.benchmark.mysql-docker.local")) {
    $MessengerEnvFile = "messenger\.env.benchmark.mysql-docker.local"
}

foreach ($requiredPath in @($RunnerEnvFile, $IdentityEnvFile, $MessengerEnvFile, "messenger\Dockerfile.benchmark-runner", "messenger\requirements-benchmark.txt", "messenger\api_tests")) {
    if (-not (Test-Path $requiredPath)) {
        throw "Missing required path: $requiredPath"
    }
}

$resolvedReportDir = Join-Path $Root $ReportDir
if (-not (Test-Path $resolvedReportDir)) {
    New-Item -ItemType Directory -Path $resolvedReportDir -Force | Out-Null
}

$runStamp = Get-Date -Format "HH-mm-ss_yyyy-MM-dd"
$hostStatsCsv = Join-Path $resolvedReportDir "${runStamp}_host_docker_stats.csv"
$gunicornLogHost = Join-Path $resolvedReportDir "${runStamp}_myna_benchmark_gunicorn_access.log"
$statsContainers = @($messengerContainer, $identityContainer, $mysqlContainer, $redisContainer)

Write-Host ""
Write-Host "Starting accurate-timing Docker-network benchmark..." -ForegroundColor Cyan

$networkExists = docker network ls --format "{{.Name}}" | Where-Object { $_ -eq $networkName }
if ($networkExists -ne $networkName) {
    docker network create $networkName | Out-Null
    Write-Host "Created Docker network: $networkName" -ForegroundColor Green
}

$mysqlRunning = docker ps --filter "name=^$mysqlContainer$" --format "{{.Names}}"
if ($mysqlRunning -ne $mysqlContainer) {
    throw "MySQL benchmark container is not running: $mysqlContainer. Start it before running this accurate benchmark."
}
Wait-MySqlReady -ContainerName $mysqlContainer -RootPassword $BenchmarkMySqlRootPassword
Repair-BenchmarkMySqlGrants `
    -ContainerName $mysqlContainer `
    -RootPassword $BenchmarkMySqlRootPassword `
    -BenchmarkUser $BenchmarkMySqlUser `
    -BenchmarkPassword $BenchmarkMySqlPassword

$redisRunning = docker ps --filter "name=^$redisContainer$" --format "{{.Names}}"
if ($redisRunning -ne $redisContainer) {
    $oldRedis = docker ps -a --filter "name=^$redisContainer$" --format "{{.Names}}"
    if ($oldRedis -eq $redisContainer) {
        docker rm -f $redisContainer | Out-Null
    }
    docker run -d --name $redisContainer --network $networkName -p 6379:6379 redis:7-alpine | Out-Null
    Assert-LastCommandOk "Start Redis"
}

foreach ($container in @($identityContainer, $messengerContainer, $runnerContainer, $precheckContainer)) {
    $old = docker ps -a --filter "name=^$container$" --format "{{.Names}}"
    if ($old -eq $container) {
        docker rm -f $container | Out-Null
    }
}

Write-Host "Building Identity image..." -ForegroundColor Cyan
docker build -t $identityImage ".\identity_service"
Assert-LastCommandOk "Build Identity image"

Write-Host "Building Messenger image..." -ForegroundColor Cyan
docker build -t $messengerImage ".\messenger"
Assert-LastCommandOk "Build Messenger image"

Write-Host "Starting Identity..." -ForegroundColor Cyan
docker run -d --name $identityContainer --network $networkName --env-file ".\$IdentityEnvFile" -p 5000:5000 $identityImage | Out-Null
Assert-LastCommandOk "Start Identity container"

Write-Host "Starting Messenger with benchmark-only Gunicorn access log..." -ForegroundColor Cyan
$messengerRunArgs = @(
    "run",
    "-d",
    "--name", $messengerContainer,
    "--network", $networkName,
    "--env-file", ".\$MessengerEnvFile"
)
$messengerRunArgs += Get-DockerEnvArgs -EnvAssignments $MessengerEnv
$messengerRunArgs += @(
    "-e", "GUNICORN_ACCESS_LOG=0",
    "-e", "GUNICORN_ACCESS_LOG_FILE=$gunicornLogContainer",
    "-e", "GUNICORN_ACCESS_LOG_FORMAT=$gunicornAccessLogFormat",
    "-e", "MYNA_BENCHMARK_ASGI_ACCESS_LOG=1",
    "-e", "MYNA_BENCHMARK_ASGI_ACCESS_LOG_FILE=$gunicornLogContainer",
    "-p", "8000:8000",
    $messengerImage
)
docker @messengerRunArgs | Out-Null
Assert-LastCommandOk "Start Messenger container"

Wait-HttpOk -Name "Identity" -Url "http://127.0.0.1:5000/api/v1/health/"
Wait-HttpOk -Name "Messenger" -Url "http://127.0.0.1:8000/api/v1/health/"

Write-Host "Building clean benchmark runner image..." -ForegroundColor Cyan
docker build -t $benchmarkRunnerImage -f ".\messenger\Dockerfile.benchmark-runner" ".\messenger"
Assert-LastCommandOk "Benchmark runner image build"

$benchmarkPath = (Resolve-Path "benchmark").Path
$apiTestsPath = (Resolve-Path "messenger\api_tests").Path
$envPath = (Resolve-Path $RunnerEnvFile).Path

docker run --rm `
    --name $precheckContainer `
    --network $networkName `
    --env-file $envPath `
    -v "${benchmarkPath}:/reports" `
    $benchmarkRunnerImage `
    -c "import urllib.request; print(urllib.request.urlopen('http://identity-service-local:5000/api/v1/health/', timeout=10).read().decode()); print(urllib.request.urlopen('http://messenger-service-local:8000/api/v1/health/', timeout=10).read().decode())"
Assert-LastCommandOk "Docker DNS precheck"

$statsJob = Start-Job -ArgumentList $hostStatsCsv, $DockerStatsIntervalMilliseconds, $statsContainers -ScriptBlock {
    param($CsvPath, $IntervalMs, $Containers)

    "timestamp,container,cpu_percent,mem_usage,mem_percent,net_io,block_io,pids" | Set-Content -Encoding UTF8 $CsvPath
    while ($true) {
        $timestamp = (Get-Date).ToString("o")
        foreach ($container in $Containers) {
            $running = docker ps --filter "name=^$container$" --format "{{.Names}}"
            if ($running -ne $container) {
                continue
            }
            $line = docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}" $container
            if (-not $line) {
                continue
            }
            $columns = $line -split ",", 7
            if ($columns.Count -lt 7) {
                continue
            }
            $cpu = $columns[1].Trim().TrimEnd("%")
            $memPercent = $columns[3].Trim().TrimEnd("%")
            $csvLine = '"{0}","{1}",{2},"{3}",{4},"{5}","{6}",{7}' -f `
                $timestamp,
                $columns[0].Trim(),
                $cpu,
                $columns[2].Trim(),
                $memPercent,
                $columns[4].Trim(),
                $columns[5].Trim(),
                $columns[6].Trim()
            Add-Content -Encoding UTF8 -Path $CsvPath -Value $csvLine
        }
        Start-Sleep -Milliseconds $IntervalMs
    }
}

$benchmarkSucceeded = $false
$benchmarkError = $null

try {
    $runnerArgs = @(
        "run",
        "--rm",
        "--name", $runnerContainer,
        "--network", $networkName,
        "--env-file", $envPath,
        "-e", "MYNA_CLEANUP_MESSENGER_DJANGO=true",
        "-e", "MYNA_MESSENGER_DOCKER_CONTAINER=",
        "-v", "${benchmarkPath}:/reports",
        "-v", "${apiTestsPath}:/app/api_tests:ro"
    )
    $runnerArgs += Get-DockerEnvArgs -EnvAssignments $RunnerEnv
    $runnerArgs += @($benchmarkRunnerImage, $BenchmarkScript)

    docker @runnerArgs
    Assert-LastCommandOk "Docker-network benchmark"
    $benchmarkSucceeded = $true
}
catch {
    $benchmarkError = $_.Exception.Message
    Write-Host "Benchmark failed: $benchmarkError" -ForegroundColor Red
}
finally {
    if ($statsJob) {
        Stop-Job $statsJob -ErrorAction SilentlyContinue
        Receive-Job $statsJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job $statsJob -Force -ErrorAction SilentlyContinue
    }
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$dockerCpOutput = docker cp "${messengerContainer}:$gunicornLogContainer" $gunicornLogHost 2>&1
$dockerCpExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference

if ($dockerCpExitCode -ne 0) {
    if ($dockerCpOutput) {
        Write-Host ($dockerCpOutput -join [Environment]::NewLine) -ForegroundColor Yellow
    }
    Write-Host "Warning: could not copy Gunicorn access log from Messenger container." -ForegroundColor Yellow
    New-Item -ItemType File -Path $gunicornLogHost -Force | Out-Null
}

$cleanupStatusPath = ""
try {
    $latestJsonBeforeCleanup = Get-LatestBenchmarkJson -Directory $resolvedReportDir
    if ($latestJsonBeforeCleanup) {
        $cleanupStatusPath = Join-Path $resolvedReportDir ($latestJsonBeforeCleanup.BaseName + "_host_side_messenger_cleanup_status.json")
    }
    & ".\scripts\cleanup-docker-mysql-benchmark-messenger.ps1" -Root $Root -StatusOutputPath $cleanupStatusPath
    if ($LASTEXITCODE -ne 0) {
        throw "Host-side Messenger cleanup failed."
    }
    if ($cleanupStatusPath) {
        & ".\scripts\patch-latest-benchmark-report-with-cleanup.ps1" -Root $Root -CleanupStatusPath $cleanupStatusPath
    }
}
catch {
    Write-Host "Cleanup/report cleanup patch failed: $($_.Exception.Message)" -ForegroundColor Yellow
    if ($cleanupStatusPath -and (Test-Path $cleanupStatusPath)) {
        try {
            & ".\scripts\patch-latest-benchmark-report-with-cleanup.ps1" -Root $Root -CleanupStatusPath $cleanupStatusPath
        }
        catch {
            Write-Host "Report patched or attempted with cleanup failure: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

$latestJson = Get-LatestBenchmarkJson -Directory $resolvedReportDir
if ($null -eq $latestJson) {
    throw "No benchmark JSON report found in $resolvedReportDir"
}

$requestGapMd = Join-Path $resolvedReportDir ($latestJson.BaseName + "_request_gap_analysis.md")

python ".\scripts\analyze-benchmark-request-gaps.py" `
    --json-report $latestJson.FullName `
    --gunicorn-log $gunicornLogHost `
    --docker-stats-csv $hostStatsCsv `
    --output-json $latestJson.FullName `
    --output-md $requestGapMd

$analyzerExit = $LASTEXITCODE
if ($analyzerExit -ne 0) {
    Write-Host "Request-gap analyzer completed with warnings or matching failure. Exit code: $analyzerExit" -ForegroundColor Yellow
}

$patchedReport = Get-Content -Raw $latestJson.FullName | ConvertFrom-Json
$gap = $patchedReport.request_gap_analysis

Write-Host ""
Write-Host "Accurate timing report files:" -ForegroundColor Cyan
Write-Host "  JSON benchmark report:         $($latestJson.FullName)" -ForegroundColor Green
Write-Host "  Patched JSON benchmark report: $($latestJson.FullName)" -ForegroundColor Green
Write-Host "  Gunicorn access log:           $gunicornLogHost" -ForegroundColor Green
Write-Host "  Host Docker stats CSV:         $hostStatsCsv" -ForegroundColor Green
Write-Host "  Markdown gap analysis:         $requestGapMd" -ForegroundColor Green

if ($gap) {
    Write-Host ""
    Write-Host "Request matching:" -ForegroundColor Cyan
    Write-Host "  matched_request_count:   $($gap.matched_request_count)" -ForegroundColor Yellow
    Write-Host "  unmatched_request_count: $($gap.unmatched_request_count)" -ForegroundColor Yellow
    Write-Host "  unmatched_percent:       $($gap.unmatched_percent)" -ForegroundColor Yellow

    if ([double]$gap.unmatched_percent -gt 10) {
        Write-Host "Warning: high unmatched request percent. Check Gunicorn access log format and benchmark request headers." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "Request matching: unavailable because request-gap analysis did not patch the JSON." -ForegroundColor Yellow
}

$runMetadata = [ordered]@{
    run_label = $RunLabel
    benchmark_script = $BenchmarkScript
    benchmark_succeeded = $benchmarkSucceeded
    benchmark_error = $benchmarkError
    analyzer_exit_code = $analyzerExit
    messenger_env = Convert-EnvAssignmentsToMap -EnvAssignments $MessengerEnv
    runner_env = Convert-EnvAssignmentsToMap -EnvAssignments $RunnerEnv
    json_report_path = $latestJson.FullName
    gap_report_path = $requestGapMd
    gunicorn_access_log_path = $gunicornLogHost
    host_docker_stats_csv_path = $hostStatsCsv
    cleanup_status_path = $cleanupStatusPath
    cleanup_success = $patchedReport.cleanup_success
    matched_request_count = if ($gap) { $gap.matched_request_count } else { $null }
    unmatched_request_count = if ($gap) { $gap.unmatched_request_count } else { $null }
    unmatched_percent = if ($gap) { $gap.unmatched_percent } else { $null }
    completed_at = (Get-Date).ToString("o")
}

if (-not [string]::IsNullOrWhiteSpace($RunMetadataOutputPath)) {
    $metadataParent = Split-Path -Parent $RunMetadataOutputPath
    if (-not [string]::IsNullOrWhiteSpace($metadataParent) -and -not (Test-Path $metadataParent)) {
        New-Item -ItemType Directory -Path $metadataParent -Force | Out-Null
    }
    $runMetadata | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $RunMetadataOutputPath
    Write-Host "  Run metadata:                 $RunMetadataOutputPath" -ForegroundColor Green
}

if (-not $benchmarkSucceeded) {
    throw "Benchmark workflow failed before cleanup/analyze completed: $benchmarkError"
}

if ($analyzerExit -ne 0) {
    throw "Request-gap analysis completed but reported matching warnings. See files above."
}
