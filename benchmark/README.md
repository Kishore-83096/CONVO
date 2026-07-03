# Benchmark Mode

Benchmark mode starts local Docker containers for Identity, Messenger, and Redis, but keeps all benchmark-specific settings out of production env files.

## Start The Stack

```powershell
.\scripts\up-benchmark.ps1
```

This creates missing real env files from the `.env.example` templates and starts:

- `identity-service-benchmark`
- `messenger-service-benchmark`
- `redis`

Containers talk to each other with Compose service names:

- `http://identity-service-benchmark:5000/api/v1`
- `http://messenger-service-benchmark:8000`
- `redis://redis:6379/0`

The Windows host and benchmark runner use exposed localhost URLs:

- `http://127.0.0.1:5000`
- `http://127.0.0.1:8000`

## Run The Benchmark

```powershell
.\scripts\run-benchmark.ps1
```

The script loads `benchmark/benchmark-runner.docker.env` into the current process and runs:

```text
messenger/api_tests/full_api_flow/myna_distributed_pairs_latency_benchmark_test.py
```

Reports are written under `files/myna_api_test_reports` by default and are ignored by Git.

## Accurate Timing Benchmark

Use this wrapper when you want client latency, Gunicorn request duration, outside-view gap, existing Messenger server timing, realtime enqueue timing, and host-side Docker stats in one report:

```powershell
.\scripts\run-local-docker-network-benchmark-accurate-timing.ps1
```

It starts the local Docker-network benchmark services with a benchmark-only Gunicorn access log, runs the distributed-pairs benchmark, collects Docker stats from host PowerShell, copies the Gunicorn log to the report directory, and patches the latest JSON report with a top-level `request_gap_analysis` section. It also writes a companion `<report-stem>_request_gap_analysis.md` summary.

The accurate runner prints these paths at the end:

- JSON benchmark report
- Patched JSON benchmark report
- Gunicorn access log
- Host Docker stats CSV
- Markdown request-gap analysis report

## Env Files

| File | Purpose |
| --- | --- |
| `identity_service/env/identity.benchmark.env` | Identity app settings for local benchmark containers. |
| `messenger/env/messenger.benchmark.env` | Messenger app settings and benchmark-safe server tuning. |
| `benchmark/benchmark-runner.docker.env` | Host-side benchmark runner URLs, levels, cleanup, report, and Docker stats settings. |

## Cleanup

The benchmark runner defaults to cleanup enabled:

```env
MYNA_CLEANUP_MESSENGER_DJANGO=true
MYNA_CLEANUP_IDENTITY_USERS=true
```

This lets the benchmark create test users, contacts, devices, messages, and rooms, then remove test data after the run. Keep cleanup enabled unless you are intentionally debugging generated data.

## Safety Warning

Do not point benchmark env files at a production database or production Identity service. The benchmark creates and deletes test users/messages and is intended only for local benchmark-safe environments.
