# Benchmark Prechecks

Use these checks before heavy local Docker benchmarks. Do not start with the
300-pair heavy run; confirm the smaller run first.

## Rebuild

```powershell
cd D:\VENV\PARROT-V2\messenger
docker build -t messenger-service:latest .
```

## Start Messenger In Benchmark Mode

If `messenger-service-local` is already running, stop it first:

```powershell
docker stop messenger-service-local
```

Start with benchmark-safe overrides:

```powershell
cd D:\VENV\PARROT-V2\messenger
docker run -d --name messenger-service-local --rm --network parrot-local -p 8000:8000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local -e DJANGO_DEBUG=False -e LOG_LEVEL=INFO -e DB_CONN_MAX_AGE=10 -e ASGI_THREADS=8 -e MYNA_PROFILE_DIRECT_SEND=true -e WEB_CONCURRENCY=5 -e GUNICORN_BACKLOG=2048 -e GUNICORN_TIMEOUT=60 -e GUNICORN_GRACEFUL_TIMEOUT=30 -e GUNICORN_KEEP_ALIVE=5 -e GUNICORN_ACCESS_LOG=0 -e IDENTITY_SERVICE_BASE_URL=http://identity-service-local:5000/api/v1 -e MESSENGER_SERVICE_BASE_URL=http://messenger-service-local:8000 -e REDIS_URL=redis://redis:6379/0 messenger-service:latest
```

## Confirm Runtime Env

```powershell
docker exec messenger-service-local sh -lc "env | sort | grep -E 'ASGI_THREADS|DB_CONN_MAX_AGE|DJANGO_DEBUG|LOG_LEVEL|WEB_CONCURRENCY|GUNICORN|REDIS_URL|IDENTITY_SERVICE_BASE_URL|MESSENGER_SERVICE_BASE_URL'"
```

Expected important values:

```text
ASGI_THREADS=8
DB_CONN_MAX_AGE=10
DJANGO_DEBUG=False
LOG_LEVEL=INFO
WEB_CONCURRENCY=5
GUNICORN_ACCESS_LOG=0
```

## Confirm Django Settings

```powershell
docker exec messenger-service-local sh -lc "python manage.py shell -c \"from django.conf import settings; print(settings.DATABASES['default'].get('CONN_MAX_AGE'))\""
```

Expected:

```text
10
```

```powershell
docker exec messenger-service-local sh -lc "python manage.py shell -c \"from django.conf import settings; print(settings.DEBUG)\""
```

Expected:

```text
False
```

## Confirm Gunicorn Command

```powershell
docker exec messenger-service-local sh -lc "ps -ef | grep gunicorn | grep -v grep"
```

Check that the command includes:

```text
--workers 5
--backlog 2048
--timeout 60
```

## Django Check

```powershell
docker exec messenger-service-local sh -lc "python manage.py check"
```

## Health Check

```powershell
curl http://127.0.0.1:8000/api/v1/health/
```

## Startup Logs

```powershell
docker logs messenger-service-local --tail 100
```

There should be no startup traceback.

## Safe Benchmark Order

First run the known-good 100-pair full ladder:

```powershell
python D:\VENV\PARROT-V2\files\run_messenger_distributed_benchmark.py docker --levels 1,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100 --pairs 100
```

Expected:

```text
PASS
0 failures
1051 total benchmark messages
100 unique rooms
no 500 responses
```

Then run a boundary test:

```powershell
python D:\VENV\PARROT-V2\files\run_messenger_distributed_benchmark.py docker --levels 100,120,150,170,200 --pairs 300
```

Only after that passes, run the heavier test:

```powershell
python D:\VENV\PARROT-V2\files\run_messenger_distributed_benchmark.py docker --levels 100,120,150,170,180,190,200,220,250,275,300 --pairs 300
```

## Post-Test Checks

After every benchmark, collect recent logs:

```powershell
docker logs messenger-service-local --since 30m > messenger_after_benchmark_logs.txt
```

Search for errors:

```powershell
Select-String -Path .\messenger_after_benchmark_logs.txt -Pattern "Traceback","Exception","OperationalError","InterfaceError","DatabaseError","too many connections","connection","500"
```

Check container resource pressure:

```powershell
docker stats messenger-service-local identity-service-local redis --no-stream
```

## Notes

`ASGI_THREADS=8` is applied by `messenger_config.asgi.DefaultExecutorCap` to the
event loop default executor in each ASGI worker. This caps default-executor
work. Thread-sensitive `sync_to_async` code may still use dedicated executors,
so this is a pressure control rather than a global thread guarantee.
