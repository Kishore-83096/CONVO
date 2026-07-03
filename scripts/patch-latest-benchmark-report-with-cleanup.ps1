param(
    [string]$Root = "D:\VENV\PARROT-V2",
    [string]$CleanupStatusPath
)

$ErrorActionPreference = "Stop"

Set-Location $Root

$reportDir = Join-Path $Root "benchmark\myna_api_test_reports"

if (-not (Test-Path $reportDir)) {
    throw "Report directory not found: $reportDir"
}

if (-not (Test-Path $CleanupStatusPath)) {
    throw "Cleanup status file not found: $CleanupStatusPath"
}

$cleanupStatus = Get-Content -Raw $CleanupStatusPath | ConvertFrom-Json

$latestJson = Get-ChildItem $reportDir -Filter "*.json" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$latestMd = Get-ChildItem $reportDir -Filter "*.md" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($null -eq $latestJson) {
    throw "No JSON benchmark report found in $reportDir"
}

Write-Host "Patching JSON report: $($latestJson.Name)" -ForegroundColor Cyan

$jsonObj = Get-Content -Raw $latestJson.FullName | ConvertFrom-Json

$jsonObj | Add-Member -NotePropertyName "host_side_messenger_cleanup" -NotePropertyValue $cleanupStatus -Force

# Final truth: benchmark cleanup is successful only if identity cleanup and host-side Messenger cleanup both succeeded.
$identityCleanupSuccess = $false

if ($jsonObj.cleanup -and $jsonObj.cleanup.identity -and $jsonObj.cleanup.identity.success -eq $true) {
    $identityCleanupSuccess = $true
}

$finalCleanupSuccess = ($identityCleanupSuccess -and $cleanupStatus.success -eq $true)

$jsonObj.cleanup_success = $finalCleanupSuccess

$jsonObj | ConvertTo-Json -Depth 100 | Set-Content -Encoding UTF8 $latestJson.FullName

if ($null -ne $latestMd) {
    Write-Host "Patching Markdown report: $($latestMd.Name)" -ForegroundColor Cyan

    $md = Get-Content -Raw $latestMd.FullName

    $statusText = if ($cleanupStatus.success -eq $true) { "True" } else { "False" }
    $messageRemovedText = if ($cleanupStatus.message_data_removed -eq $true) { "True" } else { "False" }
    $finalCleanupText = if ($finalCleanupSuccess -eq $true) { "True" } else { "False" }

    $section = @"

## Host-Side Messenger Cleanup

```json
$(($cleanupStatus | ConvertTo-Json -Depth 20))
```

**Messenger messages cleaned:** ``$messageRemovedText``  
**Host-side Messenger cleanup success:** ``$statusText``  
**Final cleanup success:** ``$finalCleanupText``  

"@

    if ($md -match "## Host-Side Messenger Cleanup") {
        $md = $md -replace "(?s)## Host-Side Messenger Cleanup.*$", $section
    } else {
        $md = $md.TrimEnd() + "`r`n" + $section
    }

    $md = $md -replace "\*\*Cleanup success:\*\* `False`", "**Cleanup success:** ``$finalCleanupText``"
    $md = $md -replace "\*\*Cleanup success:\*\* `True`", "**Cleanup success:** ``$finalCleanupText``"

    $md | Set-Content -Encoding UTF8 $latestMd.FullName
}

if ($finalCleanupSuccess -ne $true) {
    throw "Final cleanup failed. Report was patched with failure."
}

Write-Host "Report patched with successful Messenger cleanup." -ForegroundColor Green
