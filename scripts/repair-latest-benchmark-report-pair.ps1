param(
    [string]$Root = "D:\VENV\PARROT-V2"
)

$ErrorActionPreference = "Stop"

$reportDir = Join-Path $Root "benchmark\myna_api_test_reports"

if (-not (Test-Path $reportDir)) {
    throw "Report directory not found: $reportDir"
}

$reportFiles = Get-ChildItem $reportDir -File |
    Where-Object {
        ($_.Extension -in @(".json", ".md")) -and
        ($_.Name -notlike "*cleanup*status*")
    } |
    Sort-Object LastWriteTime -Descending

if (-not $reportFiles) {
    throw "No benchmark JSON/MD report files found."
}

$latestBaseName = $reportFiles[0].BaseName
$jsonPath = Join-Path $reportDir ($latestBaseName + ".json")
$mdPath = Join-Path $reportDir ($latestBaseName + ".md")
$cleanupPath = Join-Path $reportDir ($latestBaseName + "_host_side_messenger_cleanup_status.json")

if (-not (Test-Path $jsonPath)) {
    throw "Latest benchmark JSON is missing. Cannot safely repair report pair: $jsonPath"
}

$jsonObj = Get-Content -Raw $jsonPath | ConvertFrom-Json

$cleanupStatusObj = $null

if (Test-Path $cleanupPath) {
    $cleanupStatusObj = Get-Content -Raw $cleanupPath | ConvertFrom-Json
} elseif ($jsonObj.host_side_messenger_cleanup) {
    $cleanupStatusObj = $jsonObj.host_side_messenger_cleanup
} elseif ($jsonObj.cleanup -and $jsonObj.cleanup.messenger) {
    $cleanupStatusObj = $jsonObj.cleanup.messenger
}

$cleanupSuccess = $false

if ($cleanupStatusObj -and $cleanupStatusObj.success -eq $true) {
    $cleanupSuccess = $true
}

$cleanupText = if ($jsonObj.cleanup_success -eq $true -or $cleanupSuccess -eq $true) { "True" } else { "False" }
$msgCleanupText = if ($cleanupSuccess -eq $true) { "True" } else { "False" }

$cleanupJson = "{}"

if ($cleanupStatusObj) {
    $cleanupJson = $cleanupStatusObj | ConvertTo-Json -Depth 50
}

$cleanupBlockLines = @(
    "## Host-Side Messenger Cleanup",
    "",
    '```json',
    $cleanupJson,
    '```',
    "",
    ('**Messenger messages cleaned:** `{0}`  ' -f $msgCleanupText),
    ('**Messages created by benchmark removed:** `{0}`  ' -f $msgCleanupText),
    ('**Final cleanup success:** `{0}`  ' -f $cleanupText),
    ""
)

$cleanupBlock = $cleanupBlockLines -join [Environment]::NewLine

if (Test-Path $mdPath) {
    $md = Get-Content -Raw $mdPath

    $md = [regex]::Replace(
        $md,
        '\*\*Cleanup success:\*\* `(?:True|False)`',
        ('**Cleanup success:** `{0}`' -f $cleanupText)
    )

    if ($md -match "## Host-Side Messenger Cleanup") {
        $md = [regex]::Replace(
            $md,
            '(?s)## Host-Side Messenger Cleanup.*$',
            $cleanupBlock
        )
    } else {
        $md = $md.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + $cleanupBlock
    }

    $md | Set-Content -Encoding UTF8 $mdPath
} else {
    $resultText = if ($jsonObj.passed -eq $true) { "PASS" } elseif ($jsonObj.passed -eq $false) { "FAIL" } else { "UNKNOWN" }

    $summaryJson = "{}"
    if ($jsonObj.summary) {
        $summaryJson = $jsonObj.summary | ConvertTo-Json -Depth 50
    }

    $mdLines = @(
        "# Myna Distributed-Pairs Latency Benchmark Report",
        "",
        "**Result:** $resultText  ",
        ('**Run ID:** `{0}`  ' -f $jsonObj.run_id),
        ('**Service URL mode:** `{0}`  ' -f $jsonObj.service_url_mode),
        ('**Identity base URL:** `{0}`  ' -f $jsonObj.identity_base_url),
        ('**Messenger base URL:** `{0}`  ' -f $jsonObj.messenger_base_url),
        ('**Traffic mode:** `{0}`  ' -f $jsonObj.traffic_mode),
        ('**Cleanup success:** `{0}`  ' -f $cleanupText),
        "",
        "## Overall Summary",
        "",
        '```json',
        $summaryJson,
        '```',
        "",
        $cleanupBlock
    )

    $mdLines | Set-Content -Encoding UTF8 $mdPath
}

Write-Host ""
Write-Host "Verified benchmark report pair:" -ForegroundColor Green
Write-Host "  JSON: $jsonPath" -ForegroundColor Green
Write-Host "  MD:   $mdPath" -ForegroundColor Green

if (Test-Path $cleanupPath) {
    Write-Host "  Cleanup: $cleanupPath" -ForegroundColor Green
}
