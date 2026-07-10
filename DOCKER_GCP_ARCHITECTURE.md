# Myna Docker and GCP Architecture

## Local backend

Docker is the supported local backend runtime. The frontend remains outside the Compose stack.

```text
Host / Frontend / Benchmark
            |
            +--> identity:5000 (host port 5000)
            |
            +--> messenger:8000 (host port 8000)
                          |
          Identity PostgreSQL + Messenger PostgreSQL + Redis
                          |
                   Durable outbox
                          |
                 messenger-outbox
                          |
                         Redis
```

`compose.yml` owns the local backend. Long-running services are `identity-postgres`, `messenger-postgres`, `redis`, `identity`, `messenger`, and `messenger-outbox`. `identity-migrate` and `messenger-migrate` are one-shot deployment services.

> **Redis ownership:** Redis is a Messenger-only dependency for realtime/presence/cache behavior. Identity does not connect to Redis. Identity Flask-Limiter currently uses `memory://`.
There is exactly one local Messenger HTTP service. There is no local HTTP replica-count variable and no local load balancer. Local benchmarks measure one Messenger runtime under increasing request concurrency.

## Canonical images

- `identity_service/Dockerfile` builds `myna-identity:local` locally.
- `messenger/Dockerfile` builds `myna-messenger:local` locally.
- The same Messenger image runs either `MESSENGER_PROCESS_ROLE=http` or `MESSENGER_PROCESS_ROLE=outbox`.

Runtime service containers do not execute database migrations on startup. Migrations are deployment work.

## Environment ownership

- `.env` contains real local runtime secrets/configuration and GCP deployment inputs. It is not committed or copied into images.
- `.env.example` is the complete safe configuration template.
- Identity and Messenger read process environment only. Service-local `.env.local` / `.env.production` files are no longer the runtime source of truth.
- GCP scaling controls are deployment variables read by `scripts/gcp/*`; Messenger application code does not read instance counts.

## Docker DNS

Container-to-container calls use Compose service names:

- Identity -> Messenger: `http://messenger:8000`
- Messenger -> Identity: `http://identity:5000/api/v1`
- Messenger / outbox -> Messenger PostgreSQL: host `messenger-postgres` through `MESSENGER_DATABASE_URL`
- Identity -> Identity PostgreSQL: host `identity-postgres` through `IDENTITY_DATABASE_URL`
- Messenger / outbox -> Redis: host `redis`
- Benchmark -> Identity: `http://identity:5000`
- Benchmark -> Messenger: `http://messenger:8000`

`localhost` is only for host access or a process calling itself inside its own container.

## Local startup

```bash
./scripts/start-backend.sh
```

The startup flow safely stops the `myna` Compose project without `-v`, retires only known legacy Myna containers that would conflict with the canonical stack, builds changed/missing application images, starts both PostgreSQL containers and Redis, runs Identity and Messenger migrations once, starts the three long-running application roles, and waits for Identity and Messenger health.

Stop without deleting data:

```bash
./scripts/stop-backend.sh
```

## Benchmark

The benchmark is a separate root workspace under `benchmark/`. See `benchmark/README.md`.

Main command:

```bash
./benchmark/scripts/run-accurate-timing-benchmark.sh
```

The benchmark runner/orchestration/reporting code is outside Messenger. Messenger retains only server-side instrumentation that must execute inside the real process to measure Gunicorn/Django boundaries.

## GCP production target

The GCP deployment flow uses:

```text
Identity image  -> Cloud Run service
Messenger image -> Cloud Run HTTP service
Messenger image -> Cloud Run worker pool (outbox role)
Identity image  -> Cloud Run migration job
Messenger image -> Cloud Run migration job
Secrets         -> Secret Manager
Images          -> Artifact Registry
```

Cloud Run controls Messenger HTTP instance count. There is no `MESSENGER_HTTP_REPLICAS`, `HTTP_REPLICAS`, `MESSENGER_INSTANCE_COUNT`, or `REPLICA_COUNT` runtime contract.

The deployment scripts use explicit min/max instance controls and container concurrency for the Messenger Cloud Run service. The outbox worker pool uses the same Messenger image and a fixed initial worker-pool instance count that is configured separately from HTTP scaling.

GCP deployment commands:

```bash
./scripts/gcp/build-and-push.sh
./scripts/gcp/sync-secrets.sh
./scripts/gcp/deploy-all.sh
```

Before production deployment, fill all required `GCP_*` values in `.env`, especially production DB/Redis URLs and frontend origins. Private Memorystore endpoints normally require appropriate VPC egress configuration; the scripts accept `GCP_VPC_NETWORK` and `GCP_VPC_SUBNET` together.

Validate that no local replica variable entered the application or Cloud Run runtime:

```bash
./scripts/gcp/validate-no-local-replica-env.sh
```

## Data safety

Normal local stop/restart never uses `docker compose down -v` and never runs `docker system prune -a`. The canonical Compose stack uses separate named PostgreSQL volumes for Identity and Messenger plus a Redis volume. Legacy Docker volumes are not deleted. Existing MySQL data is not automatically migrated into either PostgreSQL database.
