PARROT IDENTITY - COMMAND REFERENCE
===================================

All commands use Windows PowerShell.

| Item | Value / requirement |
|---|---|
| Project directory | D:\VENV\PARROT-V2\Parrot_identity |
| Local environment file | .env.local with APP_ENV=local |
| Production environment file | .env.production with APP_ENV=production |
| Docker image | parrot-identity:latest |
| Local container | parrot-identity-local |
| Production container | parrot-identity-production |
| Service URL | http://127.0.0.1:5000 |
| Important | Local and production cannot both use host port 5000 |
| Secrets | Never commit .env.local or .env.production |
| Production | Replace every #<...> placeholder before running |


NORMAL PYTHON RUN
-----------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Open project | cd D:\VENV\PARROT-V2\Parrot_identity | Run first |
| Activate virtual environment | .\venv\Scripts\Activate.ps1 | Windows PowerShell |
| Install dependencies | python -m pip install -r requirements.txt | Run initially or after dependency changes |
| Apply database migrations | $env:APP_ENV="local"; python -m flask --app parrot_identity:app db upgrade | Run before the first local start and after model changes |
| Run local | python parrot_identity.py --env local | Loads .env.local |
| Run production settings locally | python parrot_identity.py --env production | Loads .env.production |
| Stop Python server | Ctrl+C | Use in the running terminal |


FLASK-ALEMBIC DATABASE MIGRATIONS
---------------------------------

The `migrations` directory is already initialized. Do not run `flask db init`
again. Run these commands from `D:\VENV\PARROT-V2\Parrot_identity` after
activating the virtual environment.

| Action | Exact PowerShell command | When to use it |
|---|---|---|
| Show current database revision | $env:APP_ENV="local"; python -m flask --app parrot_identity:app db current | Check which migration is applied |
| Show migration history | $env:APP_ENV="local"; python -m flask --app parrot_identity:app db history | Inspect available revisions |
| Generate an Alembic migration | $env:APP_ENV="local"; python -m flask --app parrot_identity:app db migrate -m "describe the schema change" | Run after changing SQLAlchemy models, then review the generated file |
| Apply all pending migrations | $env:APP_ENV="local"; python -m flask --app parrot_identity:app db upgrade | Run before starting the local service |
| Roll back one migration | $env:APP_ENV="local"; python -m flask --app parrot_identity:app db downgrade -1 | Use only after reviewing the downgrade operation and data impact |


DOCKER SETUP AND IMAGE
----------------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Start Docker Desktop | Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" | Wait for Docker to finish starting |
| Fix Docker command for current terminal | $env:Path += ";C:\Program Files\Docker\Docker\resources\bin" | Use only when docker is not recognized |
| Verify Docker | docker version | Must show both Client and Server |
| Open project | cd D:\VENV\PARROT-V2\Parrot_identity | Docker build context |
| Build or rebuild image | docker build -t parrot-identity:latest . | Required before first run and after code changes |
| List image | docker image ls parrot-identity | Confirms image exists |


LOCAL CONTAINER
---------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Stop production first | docker stop parrot-identity-production | Ignore not-found error |
| Create and start local | docker run -d --name parrot-identity-local --rm -p 5000:5000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local parrot-identity:latest | Loads every value from .env.local |
| Check local | docker ps -a --filter "name=parrot-identity-local" | Shows running or stopped status |
| Follow local logs | docker logs -f parrot-identity-local | Ctrl+C exits logs without stopping |
| Latest local logs | docker logs --tail 50 parrot-identity-local | Shows last 50 lines |
| Restart local | docker restart parrot-identity-local | Container must still exist |
| Stop local | docker stop parrot-identity-local | --rm automatically removes it |
| Force remove local | docker rm -f parrot-identity-local | Use for a broken container |
| Start after it was removed | docker run -d --name parrot-identity-local --rm -p 5000:5000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local parrot-identity:latest | Recreates local |


PRODUCTION CONTAINER
--------------------

Every production container start or restart runs `flask db upgrade` in
`docker_entrypoint.py` before Gunicorn starts. If migration fails, the entrypoint
exits and the application server does not start against an outdated schema.

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Stop local first | docker stop parrot-identity-local | Ignore not-found error |
| Create and start production | docker run -d --name parrot-identity-production --restart unless-stopped -p 5000:5000 --env-file .env.production -e APP_ENV=production parrot-identity:latest | Loads every value from .env.production |
| Check production | docker ps -a --filter "name=parrot-identity-production" | Shows running, stopped, or restarting |
| Follow production logs | docker logs -f parrot-identity-production | Ctrl+C exits logs without stopping |
| Latest production logs | docker logs --tail 50 parrot-identity-production | Use when startup fails |
| Start existing production | docker start parrot-identity-production | Use instead of docker run when it already exists |
| Restart production | docker restart parrot-identity-production | Keeps the same environment values |
| Stop production | docker stop parrot-identity-production | Container remains available |
| Remove production | docker rm parrot-identity-production | Container must be stopped |
| Force remove production | docker rm -f parrot-identity-production | Stops and removes it |


RELOAD ENVIRONMENT FILE CHANGES
-------------------------------

Docker does not reload an env file inside an existing container.

| Environment | Step | Exact PowerShell command |
|---|---:|---|
| Local | 1 | docker rm -f parrot-identity-local |
| Local | 2 | docker run -d --name parrot-identity-local --rm -p 5000:5000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local parrot-identity:latest |
| Production | 1 | docker rm -f parrot-identity-production |
| Production | 2 | docker run -d --name parrot-identity-production --restart unless-stopped -p 5000:5000 --env-file .env.production -e APP_ENV=production parrot-identity:latest |


REBUILD AFTER CODE OR DEPENDENCY CHANGES
----------------------------------------

| Environment | Step | Exact PowerShell command |
|---|---:|---|
| Local | 1 | docker rm -f parrot-identity-local |
| Local | 2 | docker build -t parrot-identity:latest . |
| Local | 3 | docker run -d --name parrot-identity-local --rm -p 5000:5000 --add-host=host.docker.internal:host-gateway --env-file .env.local -e APP_ENV=local parrot-identity:latest |
| Production | 1 | docker rm -f parrot-identity-production |
| Production | 2 | docker build -t parrot-identity:latest . |
| Production | 3 | docker run -d --name parrot-identity-production --restart unless-stopped -p 5000:5000 --env-file .env.production -e APP_ENV=production parrot-identity:latest |


AUTHENTICATION API
------------------

All request bodies use JSON. Login sessions expire after 24 hours and can be
ended early with logout.

| Action | Method and path | Required JSON fields |
|---|---|---|
| Register | POST /api/v1/auth/register | full_name, username, password, confirm_password |
| Login | POST /api/v1/auth/login | method (username, email, or contact_number), identifier, password |
| Logout | POST /api/v1/auth/logout | Authorization: Bearer &lt;access_token&gt; header |


HEALTH CHECKS
-------------

| Check | Exact PowerShell command |
|---|---|
| Service | Invoke-RestMethod http://127.0.0.1:5000/api/v1/health |
| MySQL | Invoke-RestMethod http://127.0.0.1:5000/api/v1/health/database |
| Cloudinary | Invoke-RestMethod http://127.0.0.1:5000/api/v1/health/cloudinary |
| Everything | Invoke-RestMethod http://127.0.0.1:5000/api/v1/health/all |
| Docker local health | docker inspect --format='{{json .State.Health}}' parrot-identity-local |
| Docker production health | docker inspect --format='{{json .State.Health}}' parrot-identity-production |


GENERAL DOCKER STATUS
---------------------

| Action | Exact PowerShell command |
|---|---|
| Running containers | docker ps |
| All containers | docker ps -a |
| Container names, status and ports | docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" |
| All images | docker image ls |
| Inspect local | docker inspect parrot-identity-local |
| Inspect production | docker inspect parrot-identity-production |


COMMON ERRORS
-------------

| Error | Exact command(s) | Resolution |
|---|---|---|
| docker is not recognized | $env:Path += ";C:\Program Files\Docker\Docker\resources\bin" | Then run docker version |
| Docker engine unavailable | Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" | Wait, then run docker version |
| Production name already in use, unchanged environment | docker start parrot-identity-production | Reuses existing container |
| Production name already in use, changed environment | docker rm -f parrot-identity-production | Then use the production docker run command |
| Local name already in use | docker rm -f parrot-identity-local | Then use the local docker run command |
| Port 5000 already allocated | docker ps --format "table {{.Names}}\t{{.Ports}}" | Stop the container currently using port 5000 |
| Production keeps restarting | docker logs --tail 50 parrot-identity-production | Correct .env.production, then recreate it |
| Local keeps restarting | docker logs --tail 50 parrot-identity-local | Correct .env.local, then recreate it |
| Render reports `Could not parse SQLAlchemy URL` | In Render Environment, set `DATABASE_URL` to the raw `postgresql://...` URL | Do not include `DATABASE_URL=`, shell commands, or placeholder text |
| Render reports `No module named psycopg2` | Rebuild and deploy the current image, and use `postgresql://...` or `postgresql+psycopg://...` for `DATABASE_URL` | The project uses Psycopg 3 and normalizes legacy Psycopg 2 URLs automatically |


CLEANUP
-------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Remove local container | docker rm -f parrot-identity-local | Safe if local is no longer needed |
| Remove production container | docker rm -f parrot-identity-production | Stops production |
| Remove image | docker image rm parrot-identity:latest | Remove containers first |


QUICK DAILY PRODUCTION WORKFLOW
-------------------------------

| Order | Action | Exact PowerShell command |
|---:|---|---|
| 1 | Start existing production | docker start parrot-identity-production |
| 2 | Check status | docker ps --filter "name=parrot-identity-production" |
| 3 | Test all dependencies | Invoke-RestMethod http://127.0.0.1:5000/api/v1/health/all |
| 4 | Follow logs | docker logs -f parrot-identity-production |
| 5 | Stop production | docker stop parrot-identity-production |
