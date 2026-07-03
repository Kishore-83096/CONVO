$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

$EnvFiles = @(
    @{ Example = "identity_service/env/identity.local-docker.env.example"; Target = "identity_service/env/identity.local-docker.env" },
    @{ Example = "identity_service/env/identity.production-local.env.example"; Target = "identity_service/env/identity.production-local.env" },
    @{ Example = "identity_service/env/identity.benchmark.env.example"; Target = "identity_service/env/identity.benchmark.env" },
    @{ Example = "identity_service/env/identity.production.example.env"; Target = "identity_service/env/identity.production.env" },
    @{ Example = "messenger/env/messenger.local-docker.env.example"; Target = "messenger/env/messenger.local-docker.env" },
    @{ Example = "messenger/env/messenger.production-local.env.example"; Target = "messenger/env/messenger.production-local.env" },
    @{ Example = "messenger/env/messenger.production-deployed-identity.env.example"; Target = "messenger/env/messenger.production-deployed-identity.env" },
    @{ Example = "messenger/env/messenger.benchmark.env.example"; Target = "messenger/env/messenger.benchmark.env" },
    @{ Example = "messenger/env/messenger.production.example.env"; Target = "messenger/env/messenger.production.env" },
    @{ Example = "benchmark/benchmark-runner.docker.env.example"; Target = "benchmark/benchmark-runner.docker.env" },
    @{ Example = "benchmark/benchmark-runner.local.env.example"; Target = "benchmark/benchmark-runner.local.env" }
)

foreach ($Pair in $EnvFiles) {
    $ExamplePath = Join-Path $RepoRoot $Pair.Example
    $TargetPath = Join-Path $RepoRoot $Pair.Target

    if (-not (Test-Path -LiteralPath $ExamplePath)) {
        throw "Missing example env file: $($Pair.Example)"
    }

    if (Test-Path -LiteralPath $TargetPath) {
        Write-Host "Exists:  $($Pair.Target)"
        continue
    }

    $TargetDirectory = Split-Path -Parent $TargetPath
    New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
    Copy-Item -LiteralPath $ExamplePath -Destination $TargetPath
    Write-Host "Created: $($Pair.Target)"
}

Write-Host ""
Write-Host "Review the real .env files and replace placeholders before running production-like services."
Write-Host "Real .env files are ignored by Git; .env.example files are the committed templates."
