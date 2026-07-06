# Linux Script Entry Points

The original automation in this repository is PowerShell-oriented. These Bash
counterparts run from the repository root on Linux and do not modify application
source code.

Use `--root /path/to/repo` when running a script from another directory.

## Local Services

```bash
./scripts/check-local-env-contract.sh
./scripts/start-local-docker-services.sh
./scripts/stop-local-docker-services.sh
./scripts/smoke-local-python-contract.sh
```

## Production Checks

```bash
./scripts/check-production-env-contract.sh
./scripts/check-production-env-contract.sh --use-examples
./scripts/run-production-smoke-test.sh \
  --identity-base-url https://identity.example.com \
  --messenger-base-url https://messenger.example.com \
  --confirm-production-smoke
```

## Benchmark Services And Runners

```bash
./scripts/start-local-docker-benchmark-services.sh
./scripts/run-local-docker-benchmark.sh
./scripts/run-local-docker-network-benchmark.sh
./scripts/run-local-docker-network-benchmark-with-verified-cleanup.sh
```

`run-local-docker-network-benchmark.sh` enables both cleanup paths:

- Identity users are deleted through the Identity API.
- Messenger benchmark data is deleted through Django inside the runner
  container. By default it reads `DATABASE_URL` from
  `messenger/.env.benchmark.local`; pass `--messenger-env-file PATH` if the
  Messenger service was started with a different env file.

For Docker-MySQL benchmark runs, start `mysql-benchmark-local` first, then run:

```bash
./scripts/start-local-docker-benchmark-mysql-services.sh
./scripts/run-local-docker-network-benchmark-accurate-timing.sh
```

Comparison wrappers:

```bash
./scripts/run-local-docker-network-endpoint-gap-comparison.sh
./scripts/run-local-docker-network-server-mode-comparison.sh
./scripts/run-local-docker-network-asgi-http-tuning-comparison.sh
```

## Notes

- Scripts use Linux paths such as `identity_service/.env.local`.
- Scripts rely on `bash`, `python3`, `curl`, and Docker CLI.
- Benchmark report patching uses Python for JSON/Markdown handling.
- Existing `.ps1` scripts are left in place for Windows users.
