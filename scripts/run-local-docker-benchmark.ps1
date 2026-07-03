param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [string]$RunnerEnvFile = "messenger\.env.benchmark.runner.local"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Pass {
    param([string]$Message)
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Load-DotEnv-ToProcess {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw "Missing env file: $Path"
    }

    $lines = Get-Content -LiteralPath $Path

    foreach ($line in $lines) {
        $trimmed = $line.Trim()

        if ([string]::IsNullOrWhiteSpace($trimmed)) {
            continue
        }

        if ($trimmed.StartsWith("#")) {
            continue
        }

        $equalIndex = $trimmed.IndexOf("=")

        if ($equalIndex -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $equalIndex).Trim()
        $value = $trimmed.Substring($equalIndex + 1).Trim()

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

function Test-Url {
    param(
        [string]$Name,
        [string]$Url
    )

    try {
        $response = Invoke-RestMethod -Uri $Url -Method GET -TimeoutSec 10
        Write-Pass "$Name reachable: $Url"
        return $response
    }
    catch {
        throw "$Name not reachable at $Url. Error: $($_.Exception.Message)"
    }
}

function Get-PythonCommand {
    param([string]$MessengerRoot)

    $venvPython = Join-Path $MessengerRoot "venv\Scripts\python.exe"
    $envPython = Join-Path $MessengerRoot "env\Scripts\python.exe"

    if (Test-Path $venvPython) {
        return $venvPython
    }

    if (Test-Path $envPython) {
        return $envPython
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue

    if ($pythonCommand) {
        return "python"
    }

    throw "Could not find Python. Expected messenger\venv, messenger\env, or python in PATH."
}

function Test-PythonImport {
    param(
        [string]$Python,
        [string]$Module
    )

    & $Python -c "import $Module" 2>$null

    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Python module available: $Module"
    } else {
        throw "Missing Python module: $Module. Install it in messenger venv, then retry."
    }
}

Set-Location $Root

Write-Step "Loading benchmark runner env"

$resolvedEnvFile = Join-Path $Root $RunnerEnvFile
Load-DotEnv-ToProcess $resolvedEnvFile

Write-Pass "Loaded env file: $resolvedEnvFile"

Write-Step "Checking required benchmark env values"

$required = @(
    "MYNA_SERVICE_URL_MODE",
    "MYNA_DOCKER_IDENTITY_BASE_URL",
    "MYNA_DOCKER_MESSENGER_BASE_URL",
    "MYNA_BENCHMARK_LEVELS",
    "MYNA_DISTRIBUTED_PAIR_COUNT",
    "MYNA_REPORT_ROOT",
    "MYNA_MESSENGER_PROJECT_ROOT"
)

foreach ($key in $required) {
    $value = [System.Environment]::GetEnvironmentVariable($key, "Process")

    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required benchmark env value: $key"
    }

    if ($key -match "SECRET|KEY|TOKEN|PASSWORD") {
        Write-Pass "$key is set"
    } else {
        Write-Pass "$key=$value"
    }
}

Write-Step "Checking Docker containers"

$identityContainer = $env:MYNA_IDENTITY_DOCKER_CONTAINER
$messengerContainer = $env:MYNA_MESSENGER_DOCKER_CONTAINER
$redisContainer = $env:MYNA_REDIS_DOCKER_CONTAINER

foreach ($container in @($identityContainer, $messengerContainer, $redisContainer)) {
    if ([string]::IsNullOrWhiteSpace($container)) {
        continue
    }

    $running = docker ps --filter "name=^$container$" --format "{{.Names}}"

    if ($running -ne $container) {
        throw "Required container is not running: $container"
    }

    Write-Pass "Container running: $container"
}

Write-Step "Checking service health through host ports"

$identityBaseUrl = $env:MYNA_DOCKER_IDENTITY_BASE_URL.TrimEnd("/")
$messengerBaseUrl = $env:MYNA_DOCKER_MESSENGER_BASE_URL.TrimEnd("/")

Test-Url "Identity health" "$identityBaseUrl/api/v1/health/" | Out-Null
Test-Url "Messenger health" "$messengerBaseUrl/api/v1/health/" | Out-Null

Write-Step "Checking Python benchmark dependencies"

$messengerRoot = Join-Path $Root "messenger"
$python = Get-PythonCommand $messengerRoot

Write-Pass "Using Python: $python"

Test-PythonImport $python "httpx"
Test-PythonImport $python "cryptography"

Write-Step "Preparing report folder"

$reportRoot = $env:MYNA_REPORT_ROOT

if (-not (Test-Path $reportRoot)) {
    New-Item -ItemType Directory -Path $reportRoot -Force | Out-Null
    Write-Pass "Created report root: $reportRoot"
} else {
    Write-Pass "Report root exists: $reportRoot"
}

Write-Step "Running benchmark"

Set-Location $messengerRoot

$benchmarkFile = "api_tests\full_api_flow\myna_distributed_pairs_latency_benchmark_test.py"

if (-not (Test-Path $benchmarkFile)) {
    throw "Benchmark file not found: $benchmarkFile"
}

Write-Host ""
Write-Host "Benchmark command:" -ForegroundColor Yellow
Write-Host "$python $benchmarkFile" -ForegroundColor Yellow
Write-Host ""

& $python $benchmarkFile

$exitCode = $LASTEXITCODE

Set-Location $Root

Write-Step "Benchmark finished"

if ($exitCode -ne 0) {
    Write-Warn "Benchmark exited with code $exitCode. Check the printed JSON summary and report files."
    exit $exitCode
}

Write-Pass "Benchmark completed successfully."

Write-Step "Latest reports"

$reportDir = Join-Path $env:MYNA_REPORT_ROOT "myna_api_test_reports"

if (Test-Path $reportDir) {
    Get-ChildItem $reportDir -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 10 Name, LastWriteTime, Length
} else {
    Write-Warn "Report directory not found yet: $reportDir"
}

Write-Host ""
Write-Host "Sprint 3 Phase 3.3 completed successfully." -ForegroundColor Green
