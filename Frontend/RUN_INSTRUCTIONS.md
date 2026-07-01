Frontend - COMMAND REFERENCE
============================

All commands use Windows PowerShell.

| Item | Value / requirement |
|---|---|
| Project directory | D:\VENV\PARROT-V2\Frontend |
| Local environment file | .env.local with VITE_APP_ENV=local |
| Production environment file | .env.production with VITE_APP_ENV=production |
| API timeout | VITE_API_TIMEOUT_MS=80000 |
| Local dev URL | http://127.0.0.1:5173 |
| Production settings local URL | http://127.0.0.1:5173 |
| Default mode | local app environment via Vite development mode |
| Production mode | Must be requested with a production script |
| Important | Local and production frontend runs cannot both use port 5173 at the same time |
| Secrets | Never commit real secret values in env files |


LOCAL RUN
---------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Open project | cd D:\VENV\PARROT-V2\Frontend | Run first |
| Install dependencies | npm install | Run initially or after dependency changes |
| Run local | npm run dev | Loads .env.local |
| Build local | npm run build | Builds with .env.local |
| Lint | npm run lint | Checks the frontend source |
| Preview local build | npm run preview | Serves the existing dist folder on http://127.0.0.1:5173 |
| Stop dev or preview server | Ctrl+C | Use in the running terminal |


PRODUCTION RUN
--------------

| Action | Exact PowerShell command | Notes |
|---|---|---|
| Open project | cd D:\VENV\PARROT-V2\Frontend | Run first |
| Install dependencies | npm install | Run initially or after dependency changes |
| Run production settings locally | npm run dev:production | Loads .env.production and serves http://127.0.0.1:5173 |
| Build production | npm run build:production | Builds with .env.production |
| Lint | npm run lint | Same lint command; lint does not use env mode |
| Preview production build | npm run preview:production | Serves the existing dist folder on http://127.0.0.1:5173 |
| Stop dev or preview server | Ctrl+C | Use in the running terminal |


MODE BEHAVIOR
-------------

Unqualified frontend commands default to local mode, matching the backend
services' default-local workflow.

Vite reserves `local` as an env-file suffix, so the frontend uses Vite's
`development` mode for local runs. The application environment still comes from
`VITE_APP_ENV=local` in `.env.local`.

Use the production-named commands when you want the frontend to read
.env.production:

```powershell
npm run dev:production
npm run build:production
npm run preview:production
```

Both local and production frontend run commands use the same browser origin:

```text
http://127.0.0.1:5173
```

This keeps the frontend origin aligned with the backend CORS allowlist.
