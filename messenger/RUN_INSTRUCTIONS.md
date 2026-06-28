Messenger Service - COMMAND REFERENCE
=====================================

All commands use Windows PowerShell.

| Item | Value / requirement |
|---|---|
| Project directory | D:\VENV\PARROT-V2\messenger |
| Local environment file | .env.local with APP_ENV=local |
| Production environment file | .env.production with APP_ENV=production |
| Docker image | messenger-service:latest |
| Local container | messenger-service-local |
| Production container | messenger-service-production |
| Service URL | http://127.0.0.1:8000 |
| Health URL | http://127.0.0.1:8000/api/v1/health/ |
| Important | Local and production cannot both use host port 8000 |
| Secrets | Never commit .env.local or .env.production |
| Production | Replace every placeholder value before running |

The messenger API contract is documented separately in
[`MYNA_MESSENGER_API_FRONTEND_E2EE_SPEC.md`](MYNA_MESSENGER_API_FRONTEND_E2EE_SPEC.md).


NORMAL PYTHON RUN
-----------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Open project | cd D:\VENV\PARROT-V2\messenger | Run first |
| Activate virtual environment | .\venv\Scripts\Activate.ps1 | Windows PowerShell |
| Install dependencies | python -m pip install -r requirements.txt | Run initially or after dependency changes |
| Apply database migrations | $env:APP_ENV="local"; python manage.py migrate | Run before the first local start and after model changes |
| Run local | $env:APP_ENV="local"; python manage.py runserver 127.0.0.1:8000 | Loads .env.local |
| Run production settings locally | $env:APP_ENV="production"; python manage.py runserver 127.0.0.1:8000 | Loads .env.production |
| Check health | Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ | Public endpoint, no JWT required |
| Stop Python server | Ctrl+C | Use in the running terminal |


DJANGO DATABASE MIGRATIONS
--------------------------

The app migrations already exist. Do not delete migration history. Run these
commands from `D:\VENV\PARROT-V2\messenger` after activating the virtual
environment.

| Action | Exact PowerShell command | When to use it |
|---|---|---|
| Show migration state | $env:APP_ENV="local"; python manage.py showmigrations | Check which migrations are applied |
| Generate migrations | $env:APP_ENV="local"; python manage.py makemigrations | Run after changing Django models, then review generated files |
| Apply all pending migrations | $env:APP_ENV="local"; python manage.py migrate | Run before starting the local service |
| Roll back one app migration | $env:APP_ENV="local"; python manage.py migrate app_name previous_migration_name | Use only after reviewing data impact |
| Run tests | $env:APP_ENV="local"; python manage.py test | Uses Django test database behavior |


DOCKER SETUP AND IMAGE
----------------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Start Docker Desktop | Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" | Wait for Docker to finish starting |
| Fix Docker command for current terminal | $env:Path += ";C:\Program Files\Docker\Docker\resources\bin" | Use only when docker is not recognized |
| Verify Docker | docker version | Must show both Client and Server |
| Open project | cd D:\VENV\PARROT-V2\messenger | Docker build context |
| Build or rebuild image | docker build -t messenger-service:latest . | Required before first run and after code changes |
| List image | docker image ls messenger-service | Confirms image exists |


LOCAL CONTAINER
---------------

Every container start runs `python manage.py migrate --noinput` in
`docker_entrypoint.py` before Gunicorn starts. If migration fails, the entrypoint
exits and the application server does not start against an outdated schema.

For local Docker, `docker_entrypoint.py` rewrites a `DATABASE_URL` host of
`127.0.0.1`, `localhost`, or `::1` to `host.docker.internal`, so the container
can reach the database running on the host machine.

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Stop production first | docker stop messenger-service-production | Ignore not-found error |
| Create and start local | docker run -d --name messenger-service-local --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local messenger-service:latest | Loads every value from .env.local |
| Check local | docker ps -a --filter "name=messenger-service-local" | Shows running or stopped status |
| Test local health | Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ | Confirms Django and Gunicorn are serving |
| Follow local logs | docker logs -f messenger-service-local | Ctrl+C exits logs without stopping |
| Latest local logs | docker logs --tail 50 messenger-service-local | Shows last 50 lines |
| Restart local | docker restart messenger-service-local | Container must still exist |
| Stop local | docker stop messenger-service-local | --rm automatically removes it |
| Force remove local | docker rm -f messenger-service-local | Use for a broken container |
| Start after it was removed | docker run -d --name messenger-service-local --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local messenger-service:latest | Recreates local |


PRODUCTION CONTAINER
--------------------

Every production container start or restart runs `python manage.py migrate
--noinput` in `docker_entrypoint.py` before Gunicorn starts.

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Stop local first | docker stop messenger-service-local | Ignore not-found error |
| Create and start production | docker run -d --name messenger-service-production --restart unless-stopped -p 8000:8000 --env-file .env.production -e APP_ENV=production messenger-service:latest | Loads every value from .env.production |
| Check production | docker ps -a --filter "name=messenger-service-production" | Shows running, stopped, or restarting |
| Test production health | Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ | Confirms container is serving |
| Follow production logs | docker logs -f messenger-service-production | Ctrl+C exits logs without stopping |
| Latest production logs | docker logs --tail 50 messenger-service-production | Use when startup fails |
| Start existing production | docker start messenger-service-production | Use instead of docker run when it already exists |
| Restart production | docker restart messenger-service-production | Keeps the same environment values |
| Stop production | docker stop messenger-service-production | Container remains available |
| Remove production | docker rm messenger-service-production | Container must be stopped |
| Force remove production | docker rm -f messenger-service-production | Stops and removes it |


RELOAD ENVIRONMENT FILE CHANGES
-------------------------------

Docker does not reload an env file inside an existing container.

| Environment | Step | Exact PowerShell command |
|---|---:|---|
| Local | 1 | docker rm -f messenger-service-local |
| Local | 2 | docker run -d --name messenger-service-local --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local messenger-service:latest |
| Production | 1 | docker rm -f messenger-service-production |
| Production | 2 | docker run -d --name messenger-service-production --restart unless-stopped -p 8000:8000 --env-file .env.production -e APP_ENV=production messenger-service:latest |


REBUILD AFTER CODE OR DEPENDENCY CHANGES
----------------------------------------

| Environment | Step | Exact PowerShell command |
|---|---:|---|
| Local | 1 | docker rm -f messenger-service-local |
| Local | 2 | docker build -t messenger-service:latest . |
| Local | 3 | docker run -d --name messenger-service-local --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local messenger-service:latest |
| Production | 1 | docker rm -f messenger-service-production |
| Production | 2 | docker build -t messenger-service:latest . |
| Production | 3 | docker run -d --name messenger-service-production --restart unless-stopped -p 8000:8000 --env-file .env.production -e APP_ENV=production messenger-service:latest |


GENERAL DOCKER STATUS
---------------------

| Action | Exact PowerShell command |
|---|---|
| Running containers | docker ps |
| All containers | docker ps -a |
| Container names, status and ports | docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" |
| All images | docker image ls |
| Inspect local | docker inspect messenger-service-local |
| Inspect production | docker inspect messenger-service-production |


COMMON ERRORS
-------------

| Error | Exact command(s) | Resolution |
|---|---|---|
| docker is not recognized | $env:Path += ";C:\Program Files\Docker\Docker\resources\bin" | Then run docker version |
| Docker engine unavailable | Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" | Wait, then run docker version |
| Production name already in use, unchanged environment | docker start messenger-service-production | Reuses existing container |
| Production name already in use, changed environment | docker rm -f messenger-service-production | Then use the production docker run command |
| Local name already in use | docker rm -f messenger-service-local | Then use the local docker run command |
| Port 8000 already allocated | docker ps --format "table {{.Names}}\t{{.Ports}}" | Stop the container currently using port 8000 |
| Production keeps restarting | docker logs --tail 50 messenger-service-production | Correct .env.production, then recreate it |
| Local keeps restarting | docker logs --tail 50 messenger-service-local | Correct .env.local, then recreate it |
| Cannot connect to local MySQL from Docker | docker logs --tail 50 messenger-service-local | Confirm MySQL is running on the host and `DATABASE_URL` uses 127.0.0.1 or localhost |
| Health check returns 400 DisallowedHost | Update DJANGO_ALLOWED_HOSTS in the selected env file | Include 127.0.0.1, localhost, and the deployed host name as needed |


CLEANUP
-------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Remove local container | docker rm -f messenger-service-local | Safe if local is no longer needed |
| Remove production container | docker rm -f messenger-service-production | Stops production |
| Remove image | docker image rm messenger-service:latest | Remove containers first |


QUICK DAILY PRODUCTION WORKFLOW
-------------------------------

| Order | Action | Exact PowerShell command |
|---:|---|---|
| 1 | Start existing production | docker start messenger-service-production |
| 2 | Check status | docker ps --filter "name=messenger-service-production" |
| 3 | Test health | Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ |
| 4 | Follow logs | docker logs -f messenger-service-production |
| 5 | Stop production | docker stop messenger-service-production |
