param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [switch]$UseExamples
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw "Missing env file: $Path"
    }

    $map = @{}

    foreach ($line in Get-Content -LiteralPath $Path) {
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
    param([AllowNull()][string]$Value)

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
        [string]$Label
    )

    if (-not $Env.ContainsKey($Key)) {
        Write-Fail "$Label missing required key: $Key"
        return
    }

    if ([string]::IsNullOrWhiteSpace($Env[$Key])) {
        Write-Fail "$Label has empty value for key: $Key"
        return
    }

    Write-Pass "$Label contains $Key"
}

function Check-Exact {
    param(
        [hashtable]$Env,
        [string]$Key,
        [string]$Expected,
        [string]$Label
    )

    if (-not $Env.ContainsKey($Key)) {
        Write-Fail "$Label missing key: $Key"
        return
    }

    $actual = $Env[$Key]

    if ($actual -eq $Expected) {
        Write-Pass "$Label.$Key = $Expected"
    } else {
        Write-Fail "$Label.$Key should be '$Expected' but is '$actual'"
    }
}

function Check-StartsWith {
    param(
        [hashtable]$Env,
        [string]$Key,
        [string]$Prefix,
        [string]$Label
    )

    if (-not $Env.ContainsKey($Key)) {
        Write-Fail "$Label missing key: $Key"
        return
    }

    $actual = $Env[$Key]

    if ($actual.StartsWith($Prefix)) {
        Write-Pass "$Label.$Key starts with $Prefix"
    } else {
        Write-Fail "$Label.$Key should start with '$Prefix' but is '$actual'"
    }
}

function Check-DoesNotContainLocalValue {
    param(
        [hashtable]$Env,
        [string]$Key,
        [string]$Label
    )

    if (-not $Env.ContainsKey($Key)) {
        Write-Fail "$Label missing key: $Key"
        return
    }

    $actual = $Env[$Key]

    $badValues = @(
        "127.0.0.1",
        "localhost",
        "host.docker.internal",
        "identity-service-local",
        "messenger-service-local",
        "redis:6379"
    )

    foreach ($bad in $badValues) {
        if ($actual -like "*$bad*") {
            Write-Fail "$Label.$Key contains production-forbidden value '$bad': $actual"
            return
        }
    }

    Write-Pass "$Label.$Key does not contain local/Docker-only hostnames"
}

function Check-PlaceholderWarning {
    param(
        [hashtable]$Env,
        [string]$Key,
        [string]$Label
    )

    if (-not $Env.ContainsKey($Key)) {
        return
    }

    $actual = $Env[$Key]

    if ($actual -like "*replace-*") {
        Write-Warn "$Label.$Key still contains placeholder: $actual"
    }
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

    if ([string]::IsNullOrWhiteSpace($leftValue) -or [string]::IsNullOrWhiteSpace($rightValue)) {
        Write-Fail "$LeftLabel.$LeftKey or $RightLabel.$RightKey is empty"
        return
    }

    $leftFingerprint = Get-SecretFingerprint $leftValue
    $rightFingerprint = Get-SecretFingerprint $rightValue

    if ($leftValue -eq $rightValue) {
        Write-Pass "$LeftLabel.$LeftKey matches $RightLabel.$RightKey fingerprint=$leftFingerprint"
    } else {
        Write-Fail "$LeftLabel.$LeftKey does NOT match $RightLabel.$RightKey"
        Write-Host "       $LeftLabel fingerprint : $leftFingerprint" -ForegroundColor DarkGray
        Write-Host "       $RightLabel fingerprint: $rightFingerprint" -ForegroundColor DarkGray
    }
}

$HasFailure = $false

Write-Host ""
Write-Host "Myna production env contract checker" -ForegroundColor Cyan
Write-Host "Root: $Root" -ForegroundColor Cyan
Write-Host ""

if ($UseExamples) {
    $identityEnvPath = Join-Path $Root "identity_service\.env.production.example"
    $messengerEnvPath = Join-Path $Root "messenger\.env.production.example"
    Write-Warn "Using .env.production.example files. Placeholder warnings are expected."
} else {
    $identityEnvPath = Join-Path $Root "identity_service\.env.production"
    $messengerEnvPath = Join-Path $Root "messenger\.env.production"
}

Write-Host ""
Write-Host "Identity env:  $identityEnvPath" -ForegroundColor Cyan
Write-Host "Messenger env: $messengerEnvPath" -ForegroundColor Cyan
Write-Host ""

$identityEnv = Read-DotEnv $identityEnvPath
$messengerEnv = Read-DotEnv $messengerEnvPath

Write-Host "Checking required Identity production keys..." -ForegroundColor Cyan

foreach ($key in @(
    "APP_ENV",
    "DATABASE_URL",
    "SECRET_KEY",
    "JWT_SECRET_KEY",
    "FRONTEND_ORIGINS",
    "MESSENGER_SERVICE_BASE_URL",
    "MESSENGER_INTERNAL_SECRET",
    "MESSENGER_POLICY_SYNC_REQUIRED"
)) {
    Require-Key $identityEnv $key "identity_service"
}

Write-Host ""
Write-Host "Checking required Messenger production keys..." -ForegroundColor Cyan

foreach ($key in @(
    "APP_ENV",
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "FRONTEND_ORIGINS",
    "DATABASE_URL",
    "REDIS_URL",
    "IDENTITY_SERVICE_BASE_URL",
    "MESSENGER_SERVICE_BASE_URL",
    "JWT_VERIFYING_KEY",
    "CONTACT_POLICY_SYNC_SECRET"
)) {
    Require-Key $messengerEnv $key "messenger"
}

Write-Host ""
Write-Host "Checking production modes..." -ForegroundColor Cyan

Check-Exact $identityEnv "APP_ENV" "production" "identity_service"
Check-Exact $messengerEnv "APP_ENV" "production" "messenger"
Check-Exact $messengerEnv "DJANGO_DEBUG" "False" "messenger"

Write-Host ""
Write-Host "Checking production URL schemes..." -ForegroundColor Cyan

Check-StartsWith $identityEnv "FRONTEND_ORIGINS" "https://" "identity_service"
Check-StartsWith $identityEnv "MESSENGER_SERVICE_BASE_URL" "https://" "identity_service"

Check-StartsWith $messengerEnv "FRONTEND_ORIGINS" "https://" "messenger"
Check-StartsWith $messengerEnv "DJANGO_CSRF_TRUSTED_ORIGINS" "https://" "messenger"
Check-StartsWith $messengerEnv "IDENTITY_SERVICE_BASE_URL" "https://" "messenger"
Check-StartsWith $messengerEnv "MESSENGER_SERVICE_BASE_URL" "https://" "messenger"

Write-Host ""
Write-Host "Checking production URLs do not contain local-only values..." -ForegroundColor Cyan

foreach ($key in @(
    "FRONTEND_ORIGINS",
    "MESSENGER_SERVICE_BASE_URL"
)) {
    Check-DoesNotContainLocalValue $identityEnv $key "identity_service"
}

foreach ($key in @(
    "FRONTEND_ORIGINS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "IDENTITY_SERVICE_BASE_URL",
    "MESSENGER_SERVICE_BASE_URL",
    "REDIS_URL"
)) {
    Check-DoesNotContainLocalValue $messengerEnv $key "messenger"
}

Write-Host ""
Write-Host "Checking shared secrets without printing them..." -ForegroundColor Cyan

if ($UseExamples) {
    Write-Warn "Skipping exact shared-secret comparison for example templates."
    Write-Warn "Real production env files must still use identical shared secrets."
} else {
    Compare-Secret `
        $identityEnv "JWT_SECRET_KEY" "identity_service" `
        $messengerEnv "JWT_VERIFYING_KEY" "messenger"

    Compare-Secret `
        $identityEnv "MESSENGER_INTERNAL_SECRET" "identity_service" `
        $messengerEnv "CONTACT_POLICY_SYNC_SECRET" "messenger"
}

Write-Host ""
Write-Host "Checking placeholders..." -ForegroundColor Cyan

foreach ($key in $identityEnv.Keys) {
    Check-PlaceholderWarning $identityEnv $key "identity_service"
}

foreach ($key in $messengerEnv.Keys) {
    Check-PlaceholderWarning $messengerEnv $key "messenger"
}

Write-Host ""
Write-Host "Secret fingerprints only, safe to paste:" -ForegroundColor Cyan
Write-Host "identity JWT_SECRET_KEY fingerprint              : $(Get-SecretFingerprint $identityEnv["JWT_SECRET_KEY"])" -ForegroundColor DarkGray
Write-Host "messenger JWT_VERIFYING_KEY fingerprint          : $(Get-SecretFingerprint $messengerEnv["JWT_VERIFYING_KEY"])" -ForegroundColor DarkGray
Write-Host "identity MESSENGER_INTERNAL_SECRET fingerprint   : $(Get-SecretFingerprint $identityEnv["MESSENGER_INTERNAL_SECRET"])" -ForegroundColor DarkGray
Write-Host "messenger CONTACT_POLICY_SYNC_SECRET fingerprint : $(Get-SecretFingerprint $messengerEnv["CONTACT_POLICY_SYNC_SECRET"])" -ForegroundColor DarkGray

Write-Host ""

if ($HasFailure) {
    Write-Host "Production env contract check FAILED." -ForegroundColor Red
    exit 1
}

Write-Host "Production env contract check PASSED." -ForegroundColor Green
exit 0

