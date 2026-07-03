$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvPath = Join-Path $RepoRoot "benchmark/benchmark-runner.docker.env"
$BenchmarkPath = Join-Path $RepoRoot "messenger/api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py"

if (-not (Test-Path -LiteralPath $EnvPath)) {
    & (Join-Path $PSScriptRoot "init-env.ps1")
}

if (-not (Test-Path -LiteralPath $BenchmarkPath)) {
    throw "Benchmark script is missing: messenger/api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py"
}

Get-Content -LiteralPath $EnvPath | ForEach-Object {
    $Line = $_.Trim()
    if (-not $Line -or $Line.StartsWith("#")) {
        return
    }

    $Name, $Value = $Line -split "=", 2
    if (-not $Name) {
        return
    }

    $CleanName = $Name.Trim()
    if ($Value -eq "") {
        [Environment]::SetEnvironmentVariable($CleanName, $null, "Process")
    } else {
        [Environment]::SetEnvironmentVariable($CleanName, $Value, "Process")
    }
}

Set-Location (Join-Path $RepoRoot "messenger")
python $BenchmarkPath
