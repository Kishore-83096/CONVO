# ASGI Runtime Tuning Notes

## Existing Local Commands

```powershell
# Start normal local benchmark services
.\scripts\start-local-docker-benchmark-mysql-services.ps1

# Run normal accurate full benchmark
.\scripts\run-local-docker-network-benchmark-accurate-timing.ps1

# Run ASGI HTTP tuning comparison
.\scripts\run-local-docker-network-asgi-http-tuning-comparison.ps1
```

## Production-Style Process Roles

Messenger API service:

```text
MESSENGER_PROCESS_ROLE=http
PORT=8000
WEB_CONCURRENCY=5
ASGI_THREADS=8
GUNICORN_BACKLOG=4096
GUNICORN_TIMEOUT=60
GUNICORN_GRACEFUL_TIMEOUT=30
GUNICORN_KEEP_ALIVE=5
GUNICORN_MAX_REQUESTS=1000
GUNICORN_MAX_REQUESTS_JITTER=100
GUNICORN_ACCESS_LOG=0
GUNICORN_ACCESS_LOGFILE=-
```

Messenger WebSocket service:

```text
MESSENGER_PROCESS_ROLE=websocket
PORT=8001
REDIS_URL=redis://redis:6379/0
```

Recommended production routing:

```text
/api/* -> Messenger API service
/ws/*  -> Messenger WebSocket service
```

The Docker image defaults to the Matrix A runtime setting: `MESSENGER_PROCESS_ROLE=http`, `WEB_CONCURRENCY=5`, `ASGI_THREADS=8`, and `GUNICORN_BACKLOG=4096`. The entrypoint still runs migrations before executing the selected role command.

## Reports

The ASGI HTTP tuning script writes:

```text
benchmark/myna_api_test_reports/asgi_http_tuning_comparison_<timestamp>.md
benchmark/myna_api_test_reports/asgi_http_tuning_comparison_<timestamp>/
```

Each matrix run still goes through the accurate timing wrapper, so it keeps producing the benchmark JSON, request gap analysis Markdown, Gunicorn access log, host Docker stats CSV, and cleanup status JSON.
