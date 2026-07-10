# Myna Accurate-Timing Benchmark

The benchmark is a root-level performance system. It calls the real Identity and Messenger APIs over the `myna-local` Docker network and does not live inside the Messenger application source tree.

## What it measures

The main runner creates independent sender/recipient pairs, saves contacts through Identity, registers E2EE devices, claims recipient prekeys, prepares encrypted direct-message payloads with the client-side benchmark cryptography helpers, and sends the real `POST /api/v1/messages/direct/` flow.

The concurrency ladder is controlled by `MYNA_BENCHMARK_LEVELS`. The default template covers `1,5,10,...,300`. `MYNA_DISTRIBUTED_PAIR_COUNT` must be at least the largest requested concurrency.

The report pipeline combines:

- client latency and throughput
- HTTPX/httpcore transport tracing
- benchmark request correlation IDs
- Gunicorn access timing
- Gunicorn gthread queue wait and worker/thread distribution
- Django/view/service timing emitted by the real Messenger process
- database execute timing
- realtime durable-outbox drain validation
- success/failure, unique message ID, duplicate ID, and matched-request validation

## Directory layout

- `runner/` — distributed-pairs benchmark client and E2EE test payload preparation
- `scripts/` — the single supported benchmark entry point
- `reporting/` — request-gap, gthread-queue, metric-definition, and Markdown report generation
- `reports/` — generated JSON and `*_README.md` reports
- `Dockerfile` / `requirements.txt` — isolated benchmark runner image; benchmark-only dependencies do not enter the production Messenger image

Messenger keeps only the timing hooks that must execute inside the real Gunicorn/Django process: `messenger_config/benchmark_gthread_worker.py` and `messenger_config/benchmark_timing.py`.

## Run

From the repository root:

```bash
./benchmark/scripts/run-accurate-timing-benchmark.sh
```

Override benchmark variables for one run without editing `.env`:

```bash
./benchmark/scripts/run-accurate-timing-benchmark.sh \
  --runner-env MYNA_DISTRIBUTED_PAIR_COUNT=100 \
  --runner-env MYNA_BENCHMARK_LEVELS=1,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100
```

The script starts the canonical Docker backend, temporarily raises local Identity rate limits and enables direct-send profiling, builds the benchmark runner image, runs traffic through Docker DNS (`identity` and `messenger`), waits for benchmark outbox events to drain, performs benchmark-created data cleanup, enriches the JSON report, generates the detailed Markdown report, and restores normal `.env` runtime settings.

## Generated reports

Reports are written to `benchmark/reports/`.

The detailed Markdown report contains the available sections from the accurate-timing pipeline, including test details, success/failure data, target-concurrency summary, server boundary decomposition, pre/post-view timing, DRF initial timing, HTTPX transport trace, Gunicorn gthread queue and worker distribution, latency decomposition, database observations, concurrent timing table, and metric definitions.

The permanent benchmark README does not hardcode current benchmark results. Measured values belong in generated report files.

## Cleanup safety

The benchmark cleans users created by the benchmark and Messenger rows associated with those benchmark users/devices. It does not run `docker system prune`, does not delete the normal Compose volumes, and does not use `docker compose down -v`.

Normal backend stop/restart preserves the separate Identity PostgreSQL, Messenger PostgreSQL, and Redis named volumes. Any future fully destructive benchmark reset must be a separate explicitly labelled script.

## Local machine limits

The benchmark measures one local Messenger HTTP container under rising request concurrency. It does not simulate Cloud Run instance scaling and does not run a local replica matrix. High levels can become constrained by the local machine's CPU, memory, Docker networking, Gunicorn execution queues, or database connection capacity; interpret those results as single-instance local capacity evidence.
