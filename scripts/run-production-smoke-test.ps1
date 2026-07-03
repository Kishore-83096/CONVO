param(
    [Parameter(Mandatory = $true)]
    [string]$IdentityBaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$MessengerBaseUrl,

    [switch]$ConfirmProductionSmoke
)

$ErrorActionPreference = "Stop"

function Assert-ProductionUrl {
    param(
        [string]$Name,
        [string]$Url
    )

    if ([string]::IsNullOrWhiteSpace($Url)) {
        throw "$Name is empty."
    }

    if (-not $Url.StartsWith("https://")) {
        throw "$Name must start with https:// for production."
    }

    $forbidden = @(
        "127.0.0.1",
        "localhost",
        "host.docker.internal",
        "identity-service-local",
        "messenger-service-local",
        "your-",
        "replace-",
        "example.com"
    )

    foreach ($bad in $forbidden) {
        if ($Url -like "*$bad*") {
            throw "$Name contains placeholder/local value: $Url"
        }
    }
}

if (-not $ConfirmProductionSmoke) {
    Write-Host ""
    Write-Host "Production smoke test was NOT started." -ForegroundColor Yellow
    Write-Host "This script creates temporary users on your production services and then deletes them." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Run again with -ConfirmProductionSmoke when you are ready." -ForegroundColor Cyan
    exit 1
}

Assert-ProductionUrl -Name "IdentityBaseUrl" -Url $IdentityBaseUrl
Assert-ProductionUrl -Name "MessengerBaseUrl" -Url $MessengerBaseUrl

$smokeScript = ".\scripts\smoke-local-python-contract.ps1"

if (-not (Test-Path $smokeScript)) {
    throw "Missing smoke script: $smokeScript. Complete Sprint 1 Phase 1.7 first."
}

Write-Host ""
Write-Host "Running production smoke test..." -ForegroundColor Cyan
Write-Host "Identity : $IdentityBaseUrl" -ForegroundColor Yellow
Write-Host "Messenger: $MessengerBaseUrl" -ForegroundColor Yellow
Write-Host ""

& $smokeScript `
    -IdentityBaseUrl $IdentityBaseUrl.TrimEnd("/") `
    -MessengerBaseUrl $MessengerBaseUrl.TrimEnd("/")

Write-Host ""
Write-Host "Production smoke test completed." -ForegroundColor Green
