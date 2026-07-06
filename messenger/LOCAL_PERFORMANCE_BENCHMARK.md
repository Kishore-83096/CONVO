# Local Performance Benchmark

This guide separates host/client URLs from container-internal service URLs.
The host browser and Windows benchmark runner can call exposed ports on
`127.0.0.1`, while backend-to-backend traffic inside Docker should use Docker
DNS names.

Do not commit real secrets. Use the `.env.*.example` files as templates and
copy secret values from your private local env files.

## Mode A: Normal Local Development

Use this mode for `python manage.py runserver` or Daphne on Windows.

```env
DJANGO_DEBUG=True
LOG_LEVEL=DEBUG
DB_CONN_MAX_AGE=0
ASGI_THREADS=8
IDENTITY_SERVICE_BASE_URL=http://127.0.0.1:5000/api/v1
MESSENGER_SERVICE_BASE_URL=http://127.0.0.1:8000
REDIS_URL=redis://127.0.0.1:6379/0
```

Host/client URLs:

```env
MYNA_IDENTITY_BASE_URL=http://127.0.0.1:5000
MYNA_MESSENGER_BASE_URL=http://127.0.0.1:8000
```

## Mode B: Local Docker Development

Use this mode when Messenger and Identity run as containers on the
`parrot-local` Docker network, but the browser or host tools still call the
published ports.

```env
DJANGO_DEBUG=True
LOG_LEVEL=DEBUG
DB_CONN_MAX_AGE=60
ASGI_THREADS=8
IDENTITY_SERVICE_BASE_URL=http://identity-service-local:5000/api/v1
MESSENGER_SERVICE_BASE_URL=http://messenger-service-local:8000
REDIS_URL=redis://redis:6379/0
```

Host/client URLs still stay on exposed localhost ports:

```env
MYNA_IDENTITY_BASE_URL=http://127.0.0.1:5000
MYNA_MESSENGER_BASE_URL=http://127.0.0.1:8000
```

## Mode C: Local Docker Benchmark

Use this mode when measuring local Docker performance. It keeps Django debug
off, keeps logging quieter, reuses database connections, disables Gunicorn
access logs, enables direct-send profiling, and samples Docker resource usage
every second through the benchmark runner.

```env
DJANGO_DEBUG=False
LOG_LEVEL=INFO
DB_CONN_MAX_AGE=10
ASGI_THREADS=8
IDENTITY_SERVICE_BASE_URL=http://identity-service-local:5000/api/v1
MESSENGER_SERVICE_BASE_URL=http://messenger-service-local:8000
REDIS_URL=redis://redis:6379/0
MYNA_PROFILE_DIRECT_SEND=true
WEB_CONCURRENCY=4
GUNICORN_BACKLOG=4096
GUNICORN_TIMEOUT=60
GUNICORN_GRACEFUL_TIMEOUT=30
GUNICORN_KEEP_ALIVE=5
GUNICORN_ACCESS_LOG=0
```

## Validation Commands

From the Messenger directory:

```powershell
cd D:\VENV\PARROT-V2\messenger
.\venv\Scripts\python.exe manage.py check
docker build -t messenger-service:latest .
```

For benchmark Docker mode, start the service with your private local env file
plus benchmark-safe overrides:

```powershell
docker run --rm --name messenger-service-local --network parrot-local -p 8000:8000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local -e DJANGO_DEBUG=False -e LOG_LEVEL=INFO -e DB_CONN_MAX_AGE=10 -e ASGI_THREADS=8 -e MYNA_PROFILE_DIRECT_SEND=true -e WEB_CONCURRENCY=4 -e GUNICORN_BACKLOG=4096 -e GUNICORN_TIMEOUT=60 -e GUNICORN_GRACEFUL_TIMEOUT=30 -e GUNICORN_KEEP_ALIVE=5 -e GUNICORN_ACCESS_LOG=0 -e IDENTITY_SERVICE_BASE_URL=http://identity-service-local:5000/api/v1 -e MESSENGER_SERVICE_BASE_URL=http://messenger-service-local:8000 -e REDIS_URL=redis://redis:6379/0 messenger-service:latest
```

Health check from the host:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/
```

Benchmark from Windows:

```powershell
python D:\VENV\PARROT-V2\files\run_messenger_distributed_benchmark.py docker --levels 1,20,40,60,80,100 --pairs 100
```

The benchmark runner defaults Docker stats to enabled with a 1-second interval:

```env
MYNA_DOCKER_STATS_ENABLED=true
MYNA_DOCKER_STATS_INTERVAL_SECONDS=1
```

`ASGI_THREADS` is applied by `messenger_config.asgi.DefaultExecutorCap` to the
event loop default executor in each ASGI worker. It caps default-executor work;
thread-sensitive `sync_to_async` sections may still use dedicated executors.
