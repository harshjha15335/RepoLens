# RepoLens deployment

The application requires a Next.js server, a Python API, persistent repository
storage, and a generation provider. Publishing the frontend alone does not
publish indexing or chat. A temporary public tunnel is running from the Windows
checkout; the application has not been moved to a remote hosting server.

## Temporary public demo (12 October 2026)

URL: https://computers-welfare-anytime-stem.trycloudflare.com

The user authorized unrestricted public access. Website HTTP 200, proxied API
health, and repository readiness were checked through this URL. The tunnel uses
Cloudflare Quick Tunnels and forwards to the existing frontend on port 3000;
the frontend proxies API requests to the backend on port 8000. Local Ollama
generation still runs on the PC and retains its CPU performance limits.

The frontend now serves an optimized production build. This remains a temporary
public demo hosted on the PC. The PC must remain awake with its
internet connection, backend, frontend and tunnel running. Stopping the tunnel
removes public access. Restarting it creates a new hostname. No cloud hosting
account or domain was created. Anyone with the URL can access the shared app.

The portable tunnel executable is installed at
`%LOCALAPPDATA%\RepoLens\tools\cloudflared.exe`. To start a new tunnel:

```powershell
& "$env:LOCALAPPDATA\RepoLens\tools\cloudflared.exe" tunnel --url http://127.0.0.1:3000 --no-autoupdate
```

The running frontend uses the separate `.next-audit` build directory. From
`frontend`, its build/start commands are:

```powershell
$env:REPOLENS_BUILD_DIR = '.next-audit'
npm run build
npm run start -- --hostname 127.0.0.1
```

Stop that frontend before rebuilding the directory it serves. The backend runs
with `APP_ENV=production` and `EMBEDDING_PROVIDER=local`, avoiding verbose SQL
logging. Ollama still uses the installed `qwen2.5-coder:latest` model.

For future development-server use, `frontend/.env.local` sets
`REPOLENS_PREVIEW_HOST` to the exact generated hostname. Update it if the tunnel
hostname changes; it controls development asset permissions, not production API
routing. The frontend configuration does not allow arbitrary development origins.

See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
for temporary-link and availability limitations.

## Docker server

Run these commands from the checkout on a server with Docker Engine and Compose:

```sh
docker compose build
docker compose up -d
docker compose exec ollama ollama pull llama3.1:8b
docker compose ps
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:3000/api/health
```

Ollama needs sufficient server memory for the selected model. The compose default
is `llama3.1:8b`; pulling a different model requires setting `LLM_MODEL` in the
backend service and recreating that service. Model downloads and uploaded
repositories persist in separate named volumes. Do not delete those volumes
when updating the app.

The frontend uses same-origin `/api` requests and proxies to `backend:8000`.
This address is set during the frontend build and supplied to its runtime.
Backend and Ollama diagnostic ports bind only to the server's loopback interface.
Local embeddings are the default; `EMBEDDING_PROVIDER` can override that setting.
Reindex repositories after changing providers.

Put an HTTPS reverse proxy in front of frontend port 3000. The current app has
shared repositories and chat sessions without per-user access control. Use
proxy authentication or a private network for a private deployment; exposing it
as an unrestricted public service exposes its shared repository data to visitors.

## Managed hosting

A managed deployment needs a hosting account and a configured backend address
at frontend build time. It also needs a persistent disk for the SQLite database,
uploaded source files and FAISS indexes. On Render, free services cannot attach
persistent disks, so an ephemeral demo loses this data after a restart or deploy.
See [Render persistent disks](https://render.com/docs/disks) and
[free service limitations](https://render.com/docs/free).

A remote backend cannot use Ollama running on the developer's localhost. Provision
a server-side model or configure a supported generation API. Without one, chat
uses the application's grounded offline fallback rather than model generation.

## Verification status

Compose configuration validation passed. Container builds and remote runtime
checks have not run: the local Docker daemon is unavailable and a hosting account
or server has not been supplied. The corrected build contexts exclude local
environment files, dependencies, caches and repository databases.
