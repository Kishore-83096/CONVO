param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [string]$RunnerEnvFile = "messenger\.env.benchmark.runner.docker-network.local"
)

$ErrorActionPreference = "Stop"

Set-Location $Root

$reportDir = Join-Path $Root "benchmark\myna_api_test_reports"
$mysqlContainer = "mysql-benchmark-local"
$messengerContainer = "messenger-service-local"
$rootPassword = "myna_root_password"
$messengerDb = "myna_messenger_benchmark"

if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}

Write-Host ""
Write-Host "Running Docker-network benchmark..." -ForegroundColor Cyan

& ".\scripts\run-local-docker-network-benchmark.ps1" -Root $Root -RunnerEnvFile $RunnerEnvFile

if ($LASTEXITCODE -ne 0) {
    throw "Benchmark failed before verified cleanup."
}

$latestJson = Get-ChildItem $reportDir -Filter "*.json" -File |
    Where-Object { $_.Name -notlike "*cleanup*status*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($null -eq $latestJson) {
    throw "No benchmark JSON report found after benchmark."
}

$latestMdPath = Join-Path $reportDir ($latestJson.BaseName + ".md")
$cleanupStatusPath = Join-Path $reportDir ($latestJson.BaseName + "_host_side_messenger_cleanup_status.json")

Write-Host ""
Write-Host "Main JSON report: $($latestJson.Name)" -ForegroundColor Yellow
Write-Host "Main MD report: $([System.IO.Path]::GetFileName($latestMdPath))" -ForegroundColor Yellow
Write-Host "Cleanup proof file: $([System.IO.Path]::GetFileName($cleanupStatusPath))" -ForegroundColor Yellow

$cleanupSuccess = $false
$cleanupMessage = ""
$cleanupStage = "starting"

try {
    Write-Host ""
    Write-Host "Cleaning Messenger benchmark messages/data from Docker MySQL..." -ForegroundColor Cyan

    foreach ($container in @($mysqlContainer, $messengerContainer)) {
        $running = docker ps --filter "name=^$container$" --format "{{.Names}}"

        if ($running -ne $container) {
            throw "Required container is not running: $container"
        }
    }

    $cleanupStage = "drop_recreate_database"

    $cleanupSql = @"
DROP DATABASE IF EXISTS myna_messenger_benchmark;
CREATE DATABASE myna_messenger_benchmark CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON myna_messenger_benchmark.* TO 'myna_benchmark'@'%';
FLUSH PRIVILEGES;
SHOW DATABASES LIKE 'myna_messenger_benchmark';
"@

    $cleanupSql | docker exec -i -e MYSQL_PWD=$rootPassword $mysqlContainer mysql -uroot

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to reset Messenger benchmark database."
    }

    $cleanupStage = "rerun_migrations"

    docker exec $messengerContainer python manage.py migrate --noinput

    if ($LASTEXITCODE -ne 0) {
        throw "Messenger migrations failed after cleanup."
    }

    $cleanupStage = "health_check"

    Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health/" -Method Get -TimeoutSec 10 | Out-Null

    $cleanupSuccess = $true
    $cleanupStage = "completed"
    $cleanupMessage = "Messenger benchmark messages/data removed successfully by dropping and recreating the Messenger benchmark database, then rerunning migrations."
}
catch {
    $cleanupSuccess = $false
    $cleanupStage = "failed"
    $cleanupMessage = $_.Exception.Message
}

$cleanupStatus = [ordered]@{
    attempted = $true
    success = $cleanupSuccess
    enabled = $true
    mode = "host_side_docker_mysql_database_reset"
    cleanup_type = "host_side_messenger_cleanup"
    cleanup_method = "drop_recreate_messenger_benchmark_database_and_rerun_migrations"
    stage = $cleanupStage
    messenger_database = $messengerDb
    mysql_container = $mysqlContainer
    messenger_container = $messengerContainer
    message_data_removed = $cleanupSuccess
    all_messenger_benchmark_data_removed = $cleanupSuccess
    messages_created_by_benchmark_removed = $cleanupSuccess
    message = $cleanupMessage
    completed_at = (Get-Date).ToString("o")
}

$cleanupStatus | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $cleanupStatusPath

$jsonObj = Get-Content -Raw $latestJson.FullName | ConvertFrom-Json
$cleanupStatusObj = Get-Content -Raw $cleanupStatusPath | ConvertFrom-Json

if (-not $jsonObj.cleanup) {
    $jsonObj | Add-Member -NotePropertyName "cleanup" -NotePropertyValue ([pscustomobject]@{}) -Force
}

$jsonObj.cleanup | Add-Member -NotePropertyName "messenger" -NotePropertyValue $cleanupStatusObj -Force
$jsonObj | Add-Member -NotePropertyName "host_side_messenger_cleanup" -NotePropertyValue $cleanupStatusObj -Force

$identityCleanupSuccess = $false

if ($jsonObj.cleanup.identity -and $jsonObj.cleanup.identity.success -eq $true) {
    $identityCleanupSuccess = $true
}

$finalCleanupSuccess = ($identityCleanupSuccess -and $cleanupStatusObj.success -eq $true)
$jsonObj.cleanup_success = $finalCleanupSuccess

$jsonObj | ConvertTo-Json -Depth 100 | Set-Content -Encoding UTF8 $latestJson.FullName

$mdCleanupText = if ($finalCleanupSuccess) { "True" } else { "False" }
$msgCleanupText = if ($cleanupSuccess) { "True" } else { "False" }
$jsonForMd = $cleanupStatusObj | ConvertTo-Json -Depth 20

$mdSection = @"

## Host-Side Messenger Cleanup

```json
$jsonForMd
```

**Messenger messages cleaned:** ``$msgCleanupText``  
**Messages created by benchmark removed:** ``$msgCleanupText``  
**Final cleanup success:** ``$mdCleanupText``  

"@

if (Test-Path $latestMdPath) {
    $md = Get-Content -Raw $latestMdPath

    $md = $md -replace '\*\*Cleanup success:\*\* `False`', "**Cleanup success:** ``$mdCleanupText``"
    $md = $md -replace '\*\*Cleanup success:\*\* `True`', "**Cleanup success:** ``$mdCleanupText``"

    if ($md -match "## Host-Side Messenger Cleanup") {
        $md = $md -replace "(?s)## Host-Side Messenger Cleanup.*$", $mdSection
    } else {
        $md = $md.TrimEnd() + "`r`n" + $mdSection
    }

    $md | Set-Content -Encoding UTF8 $latestMdPath
} else {
    $md = @"
# Myna Distributed-Pairs Latency Benchmark Report

**Result:** ``$($jsonObj.passed)``  
**Run ID:** ``$($jsonObj.run_id)``  
**Service URL mode:** ``$($jsonObj.service_url_mode)``  
**Identity base URL:** ``$($jsonObj.identity_base_url)``  
**Messenger base URL:** ``$($jsonObj.messenger_base_url)``  
**Traffic mode:** ``$($jsonObj.traffic_mode)``  
**Cleanup success:** ``$mdCleanupText``  

## Benchmark Summary

```json
$($jsonObj.summary | ConvertTo-Json -Depth 30)
```

$mdSection
"@

    $md | Set-Content -Encoding UTF8 $latestMdPath
}

Write-Host ""
Write-Host "Final files:" -ForegroundColor Cyan
Write-Host "  JSON report: $($latestJson.FullName)" -ForegroundColor Green
Write-Host "  MD report:   $latestMdPath" -ForegroundColor Green
Write-Host "  Cleanup:     $cleanupStatusPath" -ForegroundColor Green

Write-Host ""
Write-Host "Cleanup status:" -ForegroundColor Cyan
Write-Host "  Messenger cleanup attempted: true" -ForegroundColor Yellow
Write-Host "  Messenger cleanup success: $cleanupSuccess" -ForegroundColor Yellow
Write-Host "  Message data removed: $cleanupSuccess" -ForegroundColor Yellow
Write-Host "  Final cleanup success: $finalCleanupSuccess" -ForegroundColor Yellow

if ($finalCleanupSuccess -ne $true) {
    throw "Benchmark ran, but verified Messenger cleanup failed. Reports were patched with failure."
}

Write-Host ""

Write-Host ""
Write-Host "Ensuring final JSON + MD report pair exists..." -ForegroundColor Cyan
& ".\scripts\repair-latest-benchmark-report-pair.ps1" -Root $Root
Write-Host "Benchmark + verified Messenger cleanup succeeded." -ForegroundColor Green


