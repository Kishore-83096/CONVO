param(
    [string]$IdentityContainer = "identity-service-local",
    [string]$MessengerContainer = "messenger-service-local",
    [int]$ExpectedIdentityWorkers = 5,
    [int]$ExpectedMessengerWorkers = 5,
    [string]$ExpectedBacklog = "2048",
    [string]$ExpectedTimeout = "60",
    [string]$ExpectedGracefulTimeout = "30",
    [string]$ExpectedKeepAlive = "5"
)

$ErrorActionPreference = "Stop"

function Check-ContainerEnv {
    param(
        [string]$Container,
        [string]$ServiceName
    )

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "Checking env values: $ServiceName / $Container" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan

    $keys = @(
        "WEB_CONCURRENCY",
        "GUNICORN_BACKLOG",
        "GUNICORN_TIMEOUT",
        "GUNICORN_GRACEFUL_TIMEOUT",
        "GUNICORN_KEEP_ALIVE",
        "DATABASE_URL",
        "SQLALCHEMY_DATABASE_URI",
        "IDENTITY_SERVICE_BASE_URL",
        "MESSENGER_SERVICE_BASE_URL",
        "REDIS_URL"
    )

    foreach ($key in $keys) {
        $value = docker exec $Container printenv $key 2>$null

        if ($LASTEXITCODE -eq 0 -and $value) {
            $display = $value

            if ($key -match "DATABASE_URL|SQLALCHEMY_DATABASE_URI") {
                $display = $display -replace "://([^:]+):([^@]+)@", '://$1:***@'
            }

            Write-Host "  OK   $key=$display" -ForegroundColor Green
        } else {
            Write-Host "  MISS $key" -ForegroundColor DarkYellow
        }
    }
}

function Check-GunicornProcess {
    param(
        [string]$Container,
        [string]$ServiceName,
        [string]$AppMarker,
        [int]$ExpectedWorkers,
        [bool]$ShouldUseBacklog,
        [bool]$ShouldUseKeepAlive
    )

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "Checking Gunicorn runtime: $ServiceName / $Container" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan

    $pythonCode = @"
import glob
import os
import json

app_marker = "$AppMarker"

processes = []

for path in glob.glob("/proc/[0-9]*/cmdline"):
    pid = int(path.split("/")[2])

    try:
        raw_cmd = open(path, "rb").read()
        cmd = raw_cmd.replace(b"\x00", b" ").decode("utf-8", "ignore").strip()

        stat = open(f"/proc/{pid}/stat", "r").read()
        ppid = int(stat.split()[3])
    except Exception:
        continue

    if "gunicorn" in cmd and app_marker in cmd:
        processes.append({
            "pid": pid,
            "ppid": ppid,
            "cmd": cmd,
            "threads": len(os.listdir(f"/proc/{pid}/task")) if os.path.exists(f"/proc/{pid}/task") else 0,
        })

master = None
max_children = -1

for p in processes:
    child_count = sum(1 for x in processes if x["ppid"] == p["pid"])

    if child_count > max_children:
        max_children = child_count
        master = p

result = {
    "process_count": len(processes),
    "worker_count": max_children if master else 0,
    "master_pid": master["pid"] if master else None,
    "master_cmd": master["cmd"] if master else "",
    "processes": processes,
}

print(json.dumps(result, indent=2))
"@

    $raw = $pythonCode | docker exec -i $Container python -

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to inspect Gunicorn process for $ServiceName"
    }

    $result = $raw | ConvertFrom-Json

    Write-Host ""
    Write-Host "Gunicorn master PID: $($result.master_pid)" -ForegroundColor Yellow
    Write-Host "Gunicorn total processes: $($result.process_count)" -ForegroundColor Yellow
    Write-Host "Gunicorn worker count: $($result.worker_count)" -ForegroundColor Yellow

    Write-Host ""
    Write-Host "Gunicorn master command:" -ForegroundColor Yellow
    Write-Host $result.master_cmd

    $ok = $true

    if ([int]$result.worker_count -eq $ExpectedWorkers) {
        Write-Host "  OK   workers=$ExpectedWorkers" -ForegroundColor Green
    } else {
        Write-Host "  FAIL expected workers=$ExpectedWorkers but got $($result.worker_count)" -ForegroundColor Red
        $ok = $false
    }

    if ($result.master_cmd -like "*--timeout $ExpectedTimeout*") {
        Write-Host "  OK   timeout=$ExpectedTimeout" -ForegroundColor Green
    } else {
        Write-Host "  FAIL timeout $ExpectedTimeout not found in command" -ForegroundColor Red
        $ok = $false
    }

    if ($result.master_cmd -like "*--graceful-timeout $ExpectedGracefulTimeout*") {
        Write-Host "  OK   graceful-timeout=$ExpectedGracefulTimeout" -ForegroundColor Green
    } else {
        Write-Host "  FAIL graceful-timeout $ExpectedGracefulTimeout not found in command" -ForegroundColor Red
        $ok = $false
    }

    if ($ShouldUseBacklog) {
        if ($result.master_cmd -like "*--backlog $ExpectedBacklog*") {
            Write-Host "  OK   backlog=$ExpectedBacklog" -ForegroundColor Green
        } else {
            Write-Host "  FAIL backlog $ExpectedBacklog not found in command" -ForegroundColor Red
            $ok = $false
        }
    } else {
        if ($result.master_cmd -like "*--backlog*") {
            Write-Host "  OK   backlog is present" -ForegroundColor Green
        } else {
            Write-Host "  INFO backlog is not used by this service command" -ForegroundColor DarkYellow
        }
    }

    if ($ShouldUseKeepAlive) {
        if ($result.master_cmd -like "*--keep-alive $ExpectedKeepAlive*") {
            Write-Host "  OK   keep-alive=$ExpectedKeepAlive" -ForegroundColor Green
        } else {
            Write-Host "  FAIL keep-alive $ExpectedKeepAlive not found in command" -ForegroundColor Red
            $ok = $false
        }
    } else {
        if ($result.master_cmd -like "*--keep-alive*") {
            Write-Host "  OK   keep-alive is present" -ForegroundColor Green
        } else {
            Write-Host "  INFO keep-alive is not used by this service command" -ForegroundColor DarkYellow
        }
    }

    if ($ok -eq $false) {
        throw "$ServiceName Gunicorn runtime verification failed."
    }

    Write-Host ""
    Write-Host "$ServiceName Gunicorn runtime verification passed." -ForegroundColor Green
}

$identityRunning = docker ps --filter "name=^$IdentityContainer$" --format "{{.Names}}"
$messengerRunning = docker ps --filter "name=^$MessengerContainer$" --format "{{.Names}}"

if ($identityRunning -ne $IdentityContainer) {
    throw "Identity container is not running: $IdentityContainer"
}

if ($messengerRunning -ne $MessengerContainer) {
    throw "Messenger container is not running: $MessengerContainer"
}

Check-ContainerEnv -Container $IdentityContainer -ServiceName "Identity"
Check-GunicornProcess `
    -Container $IdentityContainer `
    -ServiceName "Identity" `
    -AppMarker "identity_service:app" `
    -ExpectedWorkers $ExpectedIdentityWorkers `
    -ShouldUseBacklog $false `
    -ShouldUseKeepAlive $false

Check-ContainerEnv -Container $MessengerContainer -ServiceName "Messenger"
Check-GunicornProcess `
    -Container $MessengerContainer `
    -ServiceName "Messenger" `
    -AppMarker "messenger_config.asgi:application" `
    -ExpectedWorkers $ExpectedMessengerWorkers `
    -ShouldUseBacklog $true `
    -ShouldUseKeepAlive $true

Write-Host ""
Write-Host "FINAL RESULT: serving env/runtime verification passed." -ForegroundColor Green
