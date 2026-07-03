param(
    [string]$Root = "D:\VENV\PARROT-V2"
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $map = @{}

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

        $map[$key] = $value
    }

    return $map
}

function Get-SecretFingerprint {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "empty"
    }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $hashBytes = $sha.ComputeHash($bytes)
    $hash = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLowerInvariant()

    return $hash.Substring(0, 12)
}

function Write-Pass {
    param([string]$Message)
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    $script:HasFailure = $true
}

function Require-Key {
    param(
        [hashtable]$Env,
        [string]$Key,
        [string]$FileLabel
    )

    if (-not $Env.ContainsKey($Key)) {
        Write-Fail "$FileLabel is missing required key: $Key"
        return $false
    }

    if ([string]::IsNullOrWhiteSpace($Env[$Key])) {
        Write-Fail "$FileLabel has empty value for required key: $Key"
        return $false
    }

    Write-Pass "$FileLabel contains $Key"
    return $true
}

function Compare-Secret {
    param(
        [hashtable]$LeftEnv,
        [string]$LeftKey,
        [string]$LeftLabel,
        [hashtable]$RightEnv,
        [string]$RightKey,
        [string]$RightLabel
    )

    $leftValue = $LeftEnv[$LeftKey]
    $rightValue = $RightEnv[$RightKey]

    $leftFingerprint = Get-SecretFingerprint $leftValue
    $rightFingerprint = Get-SecretFingerprint $rightValue

    if ([string]::IsNullOrWhiteSpace($leftValue) -or [string]::IsNullOrWhiteSpace($rightValue)) {
        Write-Fail "$LeftLabel.$LeftKey or $RightLabel.$RightKey is empty"
        return
    }

    if ($leftValue -eq $rightValue) {
        Write-Pass "$LeftLabel.$LeftKey matches $RightLabel.$RightKey fingerprint=$leftFingerprint"
    } else {
        Write-Fail "$LeftLabel.$LeftKey does NOT match $RightLabel.$RightKey"
        Write-Host "       $LeftLabel fingerprint : $leftFingerprint" -ForegroundColor DarkGray
        Write-Host "       $RightLabel fingerprint: $rightFingerprint" -ForegroundColor DarkGray
    }
}

function Check-Exact {
    param(
        [hashtable]$Env,
        [string]$Key,
        [string]$Expected,
        [string]$Label
    )

    if (-not $Env.ContainsKey($Key)) {
        Write-Fail "$Label is missing $Key"
        return
    }

    $actual = $Env[$Key]

    if ($actual -eq $Expected) {
        Write-Pass "$Label.$Key = $Expected"
    } else {
        Write-Fail "$Label.$Key should be '$Expected' but is '$actual'"
    }
}

function Check-Any {
    param(
        [hashtable]$Env,
        [string]$Key,
        [string[]]$Allowed,
        [string]$Label
    )

    if (-not $Env.ContainsKey($Key)) {
        Write-Fail "$Label is missing $Key"
        return
    }

    $actual = $Env[$Key]

    if ($Allowed -contains $actual) {
        Write-Pass "$Label.$Key = $actual"
    } else {
        Write-Fail "$Label.$Key should be one of '$($Allowed -join "', '")' but is '$actual'"
    }
}

function Check-StartsWith {
    param(
        [hashtable]$Env,
        [string]$Key,
        [string]$ExpectedPrefix,
        [string]$Label
    )

    if (-not $Env.ContainsKey($Key)) {
        Write-Fail "$Label is missing $Key"
        return
    }

    $actual = $Env[$Key]

    if ($actual.StartsWith($ExpectedPrefix)) {
        Write-Pass "$Label.$Key starts with $ExpectedPrefix"
    } else {
        Write-Fail "$Label.$Key should start with '$ExpectedPrefix' but is '$actual'"
    }
}

$HasFailure = $false

Write-Host ""
Write-Host "Myna local env contract checker" -ForegroundColor Cyan
Write-Host "Root: $Root" -ForegroundColor Cyan
Write-Host ""

$identityEnvPath = Join-Path $Root "identity_service\.env.local"
$messengerEnvPath = Join-Path $Root "messenger\.env.local"

Write-Host "Checking env files..." -ForegroundColor Cyan

if (Test-Path $identityEnvPath) {
    Write-Pass "Found identity_service\.env.local"
} else {
    Write-Fail "Missing identity_service\.env.local"
}

if (Test-Path $messengerEnvPath) {
    Write-Pass "Found messenger\.env.local"
} else {
    Write-Fail "Missing messenger\.env.local"
}

if ($HasFailure) {
    Write-Host ""
    Write-Host "Create missing .env.local files from the .env.local.example templates first." -ForegroundColor Yellow
    exit 1
}

$identityEnv = Read-DotEnv $identityEnvPath
$messengerEnv = Read-DotEnv $messengerEnvPath

Write-Host ""
Write-Host "Checking required Identity keys..." -ForegroundColor Cyan

Require-Key $identityEnv "APP_ENV" "identity_service\.env.local" | Out-Null
Require-Key $identityEnv "DATABASE_URL" "identity_service\.env.local" | Out-Null
Require-Key $identityEnv "SECRET_KEY" "identity_service\.env.local" | Out-Null
Require-Key $identityEnv "JWT_SECRET_KEY" "identity_service\.env.local" | Out-Null
Require-Key $identityEnv "MESSENGER_SERVICE_BASE_URL" "identity_service\.env.local" | Out-Null
Require-Key $identityEnv "MESSENGER_INTERNAL_SECRET" "identity_service\.env.local" | Out-Null

Write-Host ""
Write-Host "Checking required Messenger keys..." -ForegroundColor Cyan

Require-Key $messengerEnv "APP_ENV" "messenger\.env.local" | Out-Null
Require-Key $messengerEnv "DJANGO_SECRET_KEY" "messenger\.env.local" | Out-Null
Require-Key $messengerEnv "DATABASE_URL" "messenger\.env.local" | Out-Null
Require-Key $messengerEnv "IDENTITY_SERVICE_BASE_URL" "messenger\.env.local" | Out-Null
Require-Key $messengerEnv "MESSENGER_SERVICE_BASE_URL" "messenger\.env.local" | Out-Null
Require-Key $messengerEnv "JWT_VERIFYING_KEY" "messenger\.env.local" | Out-Null
Require-Key $messengerEnv "CONTACT_POLICY_SYNC_SECRET" "messenger\.env.local" | Out-Null
Require-Key $messengerEnv "REDIS_URL" "messenger\.env.local" | Out-Null

Write-Host ""
Write-Host "Checking shared secrets without printing them..." -ForegroundColor Cyan

Compare-Secret `
    $identityEnv "JWT_SECRET_KEY" "identity_service" `
    $messengerEnv "JWT_VERIFYING_KEY" "messenger"

Compare-Secret `
    $identityEnv "MESSENGER_INTERNAL_SECRET" "identity_service" `
    $messengerEnv "CONTACT_POLICY_SYNC_SECRET" "messenger"

Write-Host ""
Write-Host "Checking local Python service URLs..." -ForegroundColor Cyan

Check-Any $identityEnv "APP_ENV" @("local", "development") "identity_service"
Check-Any $messengerEnv "APP_ENV" @("local", "development") "messenger"

Check-Exact $identityEnv "MESSENGER_SERVICE_BASE_URL" "http://127.0.0.1:8000" "identity_service"

Check-Exact $messengerEnv "IDENTITY_SERVICE_BASE_URL" "http://127.0.0.1:5000/api/v1" "messenger"
Check-Exact $messengerEnv "MESSENGER_SERVICE_BASE_URL" "http://127.0.0.1:8000" "messenger"
Check-Exact $messengerEnv "REDIS_URL" "redis://127.0.0.1:6379/0" "messenger"

Write-Host ""
Write-Host "Checking database URL style..." -ForegroundColor Cyan

Check-StartsWith $identityEnv "DATABASE_URL" "mysql" "identity_service"
Check-StartsWith $messengerEnv "DATABASE_URL" "mysql" "messenger"

Write-Host ""
Write-Host "Secret fingerprints only, safe to paste:" -ForegroundColor Cyan

Write-Host "identity JWT_SECRET_KEY fingerprint              : $(Get-SecretFingerprint $identityEnv["JWT_SECRET_KEY"])" -ForegroundColor DarkGray
Write-Host "messenger JWT_VERIFYING_KEY fingerprint          : $(Get-SecretFingerprint $messengerEnv["JWT_VERIFYING_KEY"])" -ForegroundColor DarkGray
Write-Host "identity MESSENGER_INTERNAL_SECRET fingerprint   : $(Get-SecretFingerprint $identityEnv["MESSENGER_INTERNAL_SECRET"])" -ForegroundColor DarkGray
Write-Host "messenger CONTACT_POLICY_SYNC_SECRET fingerprint : $(Get-SecretFingerprint $messengerEnv["CONTACT_POLICY_SYNC_SECRET"])" -ForegroundColor DarkGray

Write-Host ""

if ($HasFailure) {
    Write-Host "Local env contract check FAILED." -ForegroundColor Red
    Write-Host "Fix the failed values in your real .env.local files, then run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Local env contract check PASSED." -ForegroundColor Green
exit 0
