Identity Service - COMMAND REFERENCE
===================================

All commands use Windows PowerShell.

| Item | Value / requirement |
|---|---|
| Project directory | D:\VENV\Myna-V2\identity_service |
| Local environment file | .env.local with APP_ENV=local |
| Production environment file | .env.production with APP_ENV=production |
| Docker image | identity-service:latest |
| Local container | identity-service-local |
| Production container | identity-service-production |
| Service URL | http://127.0.0.1:5000 |
| Base URL behavior | `/` redirects to `/api/v1/health/all` in local and production |
| Important | Local and production cannot both use host port 5000 |
| Secrets | Never commit .env.local or .env.production |
| Production | Replace every #<...> placeholder before running |

API endpoints and Postman examples are documented separately in
[`API_DOCUMENTATION.md`](API_DOCUMENTATION.md).


NORMAL PYTHON RUN
-----------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Open project | cd D:\VENV\Myna-V2\identity_service | Run first |
| Activate virtual environment | .\venv\Scripts\Activate.ps1 | Windows PowerShell |
| Install dependencies | python -m pip install -r requirements.txt | Run initially or after dependency changes |
| Apply database migrations | $env:APP_ENV="local"; python -m flask --app identity_service:app db upgrade | Run before the first local start and after model changes |
| Run local | python identity_service.py --env local | Loads .env.local |
| Run production settings locally | python identity_service.py --env production | Loads .env.production |
| Stop Python server | Ctrl+C | Use in the running terminal |


FLASK-ALEMBIC DATABASE MIGRATIONS
---------------------------------

The `migrations` directory is already initialized. Do not run `flask db init`
again. Run these commands from `D:\VENV\Myna-V2\identity_service` after
activating the virtual environment.

| Action | Exact PowerShell command | When to use it |
|---|---|---|
| Show current database revision | $env:APP_ENV="local"; python -m flask --app identity_service:app db current | Check which migration is applied |
| Show migration history | $env:APP_ENV="local"; python -m flask --app identity_service:app db history | Inspect available revisions |
| Generate an Alembic migration | $env:APP_ENV="local"; python -m flask --app identity_service:app db migrate -m "describe the schema change" | Run after changing SQLAlchemy models, then review the generated file |
| Apply all pending migrations | $env:APP_ENV="local"; python -m flask --app identity_service:app db upgrade | Run before starting the local service |
| Roll back one migration | $env:APP_ENV="local"; python -m flask --app identity_service:app db downgrade -1 | Use only after reviewing the downgrade operation and data impact |


DOCKER SETUP AND IMAGE
----------------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Start Docker Desktop | Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" | Wait for Docker to finish starting |
| Fix Docker command for current terminal | $env:Path += ";C:\Program Files\Docker\Docker\resources\bin" | Use only when docker is not recognized |
| Verify Docker | docker version | Must show both Client and Server |
| Open project | cd D:\VENV\Myna-V2\identity_service | Docker build context |
| Build or rebuild image | docker build -t identity-service:latest . | Required before first run and after code changes |
| List image | docker image ls identity-service | Confirms image exists |


LOCAL CONTAINER
---------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Stop production first | docker stop identity-service-production | Ignore not-found error |
| Create and start local | docker run -d --name identity-service-local --rm -p 5000:5000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local identity-service:latest | Loads every value from .env.local |
| Check local | docker ps -a --filter "name=identity-service-local" | Shows running or stopped status |
| Follow local logs | docker logs -f identity-service-local | Ctrl+C exits logs without stopping |
| Latest local logs | docker logs --tail 50 identity-service-local | Shows last 50 lines |
| Restart local | docker restart identity-service-local | Container must still exist |
| Stop local | docker stop identity-service-local | --rm automatically removes it |
| Force remove local | docker rm -f identity-service-local | Use for a broken container |
| Start after it was removed | docker run -d --name identity-service-local --rm -p 5000:5000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local identity-service:latest | Recreates local |


PRODUCTION CONTAINER
--------------------

Every production container start or restart runs `flask db upgrade` in
`docker_entrypoint.py` before Gunicorn starts. If migration fails, the entrypoint
exits and the application server does not start against an outdated schema.

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Stop local first | docker stop identity-service-local | Ignore not-found error |
| Create and start production | docker run -d --name identity-service-production --restart unless-stopped -p 5000:5000 --env-file .env.production -e APP_ENV=production identity-service:latest | Loads every value from .env.production |
| Check production | docker ps -a --filter "name=identity-service-production" | Shows running, stopped, or restarting |
| Follow production logs | docker logs -f identity-service-production | Ctrl+C exits logs without stopping |
| Latest production logs | docker logs --tail 50 identity-service-production | Use when startup fails |
| Start existing production | docker start identity-service-production | Use instead of docker run when it already exists |
| Restart production | docker restart identity-service-production | Keeps the same environment values |
| Stop production | docker stop identity-service-production | Container remains available |
| Remove production | docker rm identity-service-production | Container must be stopped |
| Force remove production | docker rm -f identity-service-production | Stops and removes it |


RELOAD ENVIRONMENT FILE CHANGES
-------------------------------

Docker does not reload an env file inside an existing container.

| Environment | Step | Exact PowerShell command |
|---|---:|---|
| Local | 1 | docker rm -f identity-service-local |
| Local | 2 | docker run -d --name identity-service-local --rm -p 5000:5000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local identity-service:latest |
| Production | 1 | docker rm -f identity-service-production |
| Production | 2 | docker run -d --name identity-service-production --restart unless-stopped -p 5000:5000 --env-file .env.production -e APP_ENV=production identity-service:latest |


REBUILD AFTER CODE OR DEPENDENCY CHANGES
----------------------------------------

| Environment | Step | Exact PowerShell command |
|---|---:|---|
| Local | 1 | docker rm -f identity-service-local |
| Local | 2 | docker build -t identity-service:latest . |
| Local | 3 | docker run -d --name identity-service-local --rm -p 5000:5000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local identity-service:latest |
| Production | 1 | docker rm -f identity-service-production |
| Production | 2 | docker build -t identity-service:latest . |
| Production | 3 | docker run -d --name identity-service-production --restart unless-stopped -p 5000:5000 --env-file .env.production -e APP_ENV=production identity-service:latest |


GENERAL DOCKER STATUS
---------------------

| Action | Exact PowerShell command |
|---|---|
| Running containers | docker ps |
| All containers | docker ps -a |
| Container names, status and ports | docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" |
| All images | docker image ls |
| Inspect local | docker inspect identity-service-local |
| Inspect production | docker inspect identity-service-production |


COMMON ERRORS
-------------

| Error | Exact command(s) | Resolution |
|---|---|---|
| docker is not recognized | $env:Path += ";C:\Program Files\Docker\Docker\resources\bin" | Then run docker version |
| Docker engine unavailable | Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" | Wait, then run docker version |
| Production name already in use, unchanged environment | docker start identity-service-production | Reuses existing container |
| Production name already in use, changed environment | docker rm -f identity-service-production | Then use the production docker run command |
| Local name already in use | docker rm -f identity-service-local | Then use the local docker run command |
| Port 5000 already allocated | docker ps --format "table {{.Names}}\t{{.Ports}}" | Stop the container currently using port 5000 |
| Production keeps restarting | docker logs --tail 50 identity-service-production | Correct .env.production, then recreate it |
| Local keeps restarting | docker logs --tail 50 identity-service-local | Correct .env.local, then recreate it |
| Render reports `Could not parse SQLAlchemy URL` | In Render Environment, set `DATABASE_URL` to the raw `postgresql://...` URL | Do not include `DATABASE_URL=`, shell commands, or placeholder text |
| Render reports `No module named psycopg2` | Rebuild and deploy the current image, and use `postgresql://...` or `postgresql+psycopg://...` for `DATABASE_URL` | The project uses Psycopg 3 and normalizes legacy Psycopg 2 URLs automatically |


CLEANUP
-------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Remove local container | docker rm -f identity-service-local | Safe if local is no longer needed |
| Remove production container | docker rm -f identity-service-production | Stops production |
| Remove image | docker image rm identity-service:latest | Remove containers first |


QUICK DAILY PRODUCTION WORKFLOW
-------------------------------

| Order | Action | Exact PowerShell command |
|---:|---|---|
| 1 | Start existing production | docker start identity-service-production |
| 2 | Check status | docker ps --filter "name=identity-service-production" |
| 3 | Test all dependencies | Invoke-RestMethod http://127.0.0.1:5000/api/v1/health/all |
| 4 | Follow logs | docker logs -f identity-service-production |
| 5 | Stop production | docker stop identity-service-production |
