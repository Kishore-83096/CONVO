param(
    [string]$IdentityBaseUrl = "http://127.0.0.1:5000",
    [string]$MessengerBaseUrl = "http://127.0.0.1:8000"
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

function Write-Fail {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Convert-ToJsonBody {
    param([hashtable]$Body)
    return ($Body | ConvertTo-Json -Depth 20)
}

function Invoke-Json {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,

        [Parameter(Mandatory = $true)]
        [string]$Url,

        [hashtable]$Body,

        [string]$Token
    )

    $headers = @{
        "Content-Type" = "application/json"
    }

    if (-not [string]::IsNullOrWhiteSpace($Token)) {
        $headers["Authorization"] = "Bearer $Token"
    }

    $params = @{
        Method = $Method
        Uri = $Url
        Headers = $headers
    }

    if ($null -ne $Body) {
        $params["Body"] = Convert-ToJsonBody $Body
    }

    try {
        return Invoke-RestMethod @params
    }
    catch {
        Write-Host ""
        Write-Fail "Request failed:"
        Write-Host "$Method $Url" -ForegroundColor Yellow

        if ($_.Exception.Response) {
            Write-Host "Status: $([int]$_.Exception.Response.StatusCode) $($_.Exception.Response.StatusCode)" -ForegroundColor Yellow

            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $responseText = $reader.ReadToEnd()
                Write-Host "Response body:" -ForegroundColor Yellow
                Write-Host $responseText
            }
            catch {
                Write-Host "Could not read response body."
            }
        } else {
            Write-Host $_.Exception.Message -ForegroundColor Yellow
        }

        throw
    }
}

function New-TestUserPayload {
    param(
        [string]$Prefix,
        [string]$RunId,
        [string]$Password
    )

    $username = "$Prefix$RunId".ToLowerInvariant()

    return @{
        full_name = "Smoke Test $Prefix"
        username = $username
        password = $Password
        confirm_password = $Password
    }
}

function Register-TestUser {
    param(
        [hashtable]$Payload
    )

    return Invoke-Json `
        -Method "POST" `
        -Url "$IdentityBaseUrl/api/v1/auth/register" `
        -Body $Payload
}

function Login-TestUser {
    param(
        [string]$Username,
        [string]$Password
    )

    return Invoke-Json `
        -Method "POST" `
        -Url "$IdentityBaseUrl/api/v1/auth/login" `
        -Body @{
            method = "username"
            identifier = $Username
            password = $Password
        }
}

function Delete-TestUser {
    param(
        [string]$Token,
        [object]$User,
        [string]$Password
    )

    return Invoke-Json `
        -Method "DELETE" `
        -Url "$IdentityBaseUrl/api/v1/auth/delete-account" `
        -Token $Token `
        -Body @{
            username = [string]$User.username
            email = [string]$User.email
            contact_number = [string]$User.contact_number
            current_password = $Password
        }
}

$runId = ((Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")) + (Get-Random -Minimum 100 -Maximum 999)
$password = "SmokeTest@12345"

$userARegisterPayload = New-TestUserPayload -Prefix "smokea" -RunId $runId -Password $password
$userBRegisterPayload = New-TestUserPayload -Prefix "smokeb" -RunId $runId -Password $password

$userA = $null
$userB = $null
$tokenA = $null
$tokenB = $null

try {
    Write-Step "Checking Identity health"
    $identityHealth = Invoke-RestMethod "$IdentityBaseUrl/api/v1/health/"
    Write-Pass "Identity health OK: $($identityHealth.service)"

    Write-Step "Checking Messenger health"
    $messengerHealth = Invoke-RestMethod "$MessengerBaseUrl/api/v1/health/"
    Write-Pass "Messenger health OK: $($messengerHealth.service)"

    Write-Step "Registering temporary Identity users"
    $registeredA = Register-TestUser -Payload $userARegisterPayload
    $registeredB = Register-TestUser -Payload $userBRegisterPayload

    $userA = $registeredA.data
    $userB = $registeredB.data

    Write-Pass "Registered user A: $($userA.username), contact_number=$($userA.contact_number)"
    Write-Pass "Registered user B: $($userB.username), contact_number=$($userB.contact_number)"

    Write-Step "Logging in temporary users"
    $loginA = Login-TestUser -Username $userA.username -Password $password
    $loginB = Login-TestUser -Username $userB.username -Password $password

    $tokenA = $loginA.data.access_token
    $tokenB = $loginB.data.access_token

    if ([string]::IsNullOrWhiteSpace($tokenA) -or [string]::IsNullOrWhiteSpace($tokenB)) {
        throw "Login did not return access tokens."
    }

    Write-Pass "Login returned access tokens"

    Write-Step "Checking Messenger JWT verification using /api/v1/auth/whoami/"
    $whoamiA = Invoke-Json `
        -Method "GET" `
        -Url "$MessengerBaseUrl/api/v1/auth/whoami/" `
        -Token $tokenA

    if (-not $whoamiA.authenticated) {
        throw "Messenger whoami did not authenticate user A."
    }

    Write-Pass "Messenger accepted Identity JWT for user_id=$($whoamiA.user_id)"

    Write-Step "Adding user B as contact of user A through Identity"
    $addContact = Invoke-Json `
        -Method "POST" `
        -Url "$IdentityBaseUrl/api/v1/contacts" `
        -Token $tokenA `
        -Body @{
            contact_number = [string]$userB.contact_number
            saved_name = "Smoke Contact B"
        }

    $contactId = $addContact.data.id

    if (-not $contactId) {
        throw "Contact add did not return contact id."
    }

    Write-Pass "Contact added in Identity. contact_id=$contactId"

    Write-Step "Blocking contact to verify Identity -> Messenger policy sync"
    $blockResult = Invoke-Json `
        -Method "PATCH" `
        -Url "$IdentityBaseUrl/api/v1/contacts/$contactId/block" `
        -Token $tokenA `
        -Body @{
            is_blocked = $true
        }

    if (-not $blockResult.success) {
        throw "Block contact did not return success=true."
    }

    Write-Pass "Block policy synced successfully"

    Write-Step "Unblocking contact"
    $unblockResult = Invoke-Json `
        -Method "PATCH" `
        -Url "$IdentityBaseUrl/api/v1/contacts/$contactId/block" `
        -Token $tokenA `
        -Body @{
            is_blocked = $false
        }

    if (-not $unblockResult.success) {
        throw "Unblock contact did not return success=true."
    }

    Write-Pass "Unblock policy synced successfully"

    Write-Step "Ghosting contact to verify ghost policy sync"
    $ghostResult = Invoke-Json `
        -Method "PATCH" `
        -Url "$IdentityBaseUrl/api/v1/contacts/$contactId/ghost" `
        -Token $tokenA `
        -Body @{
            is_ghosted = $true
            duration = "1h"
        }

    if (-not $ghostResult.success) {
        throw "Ghost contact did not return success=true."
    }

    Write-Pass "Ghost policy synced successfully"

    Write-Step "Unghosting contact"
    $unghostResult = Invoke-Json `
        -Method "PATCH" `
        -Url "$IdentityBaseUrl/api/v1/contacts/$contactId/ghost" `
        -Token $tokenA `
        -Body @{
            is_ghosted = $false
            duration = "1h"
        }

    if (-not $unghostResult.success) {
        throw "Unghost contact did not return success=true."
    }

    Write-Pass "Unghost policy synced successfully"

    Write-Host ""
    Write-Host "Local Python Identity <-> Messenger smoke test PASSED." -ForegroundColor Green
}
finally {
    Write-Host ""
    Write-Host "Cleanup starting..." -ForegroundColor Cyan

    if ($tokenA -and $userA) {
        try {
            Delete-TestUser -Token $tokenA -User $userA -Password $password | Out-Null
            Write-Pass "Deleted temporary user A"
        }
        catch {
            Write-Host "[WARN] Could not delete temporary user A: $($userA.username)" -ForegroundColor Yellow
        }
    }

    if ($tokenB -and $userB) {
        try {
            Delete-TestUser -Token $tokenB -User $userB -Password $password | Out-Null
            Write-Pass "Deleted temporary user B"
        }
        catch {
            Write-Host "[WARN] Could not delete temporary user B: $($userB.username)" -ForegroundColor Yellow
        }
    }

    Write-Host "Cleanup completed." -ForegroundColor Cyan
}
