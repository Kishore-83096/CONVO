param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [string]$StatusOutputPath = ""
)

$ErrorActionPreference = "Stop"

$mysqlContainer = "mysql-benchmark-local"
$messengerContainer = "messenger-service-local"
$rootPassword = "myna_root_password"
$messengerDb = "myna_messenger_benchmark"
$benchmarkUser = "myna_benchmark"

function Write-CleanupStatus {
    param(
        [bool]$Success,
        [string]$Message,
        [string]$Stage
    )

    $status = [ordered]@{
        attempted = $true
        success = $Success
        cleanup_type = "host_side_messenger_cleanup"
        cleanup_method = "drop_recreate_messenger_benchmark_database_and_rerun_migrations"
        stage = $Stage
        messenger_database = $messengerDb
        mysql_container = $mysqlContainer
        messenger_container = $messengerContainer
        message_data_removed = $Success
        all_messenger_benchmark_data_removed = $Success
        message = $Message
        completed_at = (Get-Date).ToString("o")
    }

    if ($StatusOutputPath -ne "") {
        $status | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $StatusOutputPath
    }

    return $status
}

Set-Location $Root

try {
    Write-Host ""
    Write-Host "Cleaning Messenger benchmark messages/data from Docker MySQL..." -ForegroundColor Cyan

    foreach ($container in @($mysqlContainer, $messengerContainer)) {
        $running = docker ps --filter "name=^$container$" --format "{{.Names}}"

        if ($running -ne $container) {
            throw "Required container is not running: $container"
        }
    }

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

    Write-Host "Messenger benchmark database reset." -ForegroundColor Green

    Write-Host ""
    Write-Host "Re-running Messenger migrations after cleanup..." -ForegroundColor Cyan

    docker exec $messengerContainer python manage.py migrate --noinput

    if ($LASTEXITCODE -ne 0) {
        throw "Messenger migrations failed after cleanup."
    }

    Write-Host "Messenger migrations completed." -ForegroundColor Green

    Write-Host ""
    Write-Host "Checking Messenger health after cleanup..." -ForegroundColor Cyan

    Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health/" -Method Get -TimeoutSec 10 | Out-Null

    $status = Write-CleanupStatus -Success $true -Message "Messenger benchmark messages/data removed successfully." -Stage "completed"

    Write-Host "Messenger cleanup completed successfully." -ForegroundColor Green

    exit 0
}
catch {
    $errorMessage = $_.Exception.Message

    Write-CleanupStatus -Success $false -Message $errorMessage -Stage "failed" | Out-Null

    Write-Host "Messenger cleanup failed: $errorMessage" -ForegroundColor Red

    exit 1
}
