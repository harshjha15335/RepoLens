# RepoLens deployment

RepoLens runs as one shared owner workspace. Every browser user who knows the
owner key can access the same repositories and chat sessions. There are no
per-user accounts or data isolation boundaries. Keep public deployments behind
access controls appropriate for this shared data model.

## Configure owner access

Set `REPOLENS_ACCESS_KEY` to a random secret with at least 32 characters. The
backend refuses to start without it.

- For local development, put the key in `backend/.env`; settings load `.env`
  relative to the backend working directory.
- For Docker Compose, put the key in a root `.env` file or export it in the
  environment before running Compose. Compose requires the variable.

The browser UI signs in with the owner key and receives an HTTP-only session
cookie. Native clients should send `Authorization: Bearer <key>` with each API
request. Interactive API documentation and OpenAPI endpoints are disabled.
`/api/health` and `/api/auth/status` remain available without signing in.

Use one backend process and worker. Indexing jobs rely on a single in-process
worker and are not coordinated across multiple backend instances. When the
backend restarts, unfinished indexing and evaluation jobs are marked `FAILED`;
they do not resume automatically. Reindex the repository or rerun the
evaluation manually.

## Local development

From the repository root:

```powershell
Copy-Item .env.example backend/.env
# Edit backend/.env and set REPOLENS_ACCESS_KEY to a random secret of 32+ characters.
cd backend
uvicorn app.main:app --reload --port 8000
```

The default maximum upload size is 50 MB (`MAX_UPLOAD_MB`). For predictable
offline embedding behavior, set `EMBEDDING_PROVIDER=local`. The Sentence
Transformers provider loads a model only from the local cache and never
downloads one automatically. Changing embedding providers or models requires
reindexing existing repositories. Dense indexes created before embedding
metadata was saved are legacy indexes and also require reindexing before dense
retrieval.

## Docker Compose

Put `REPOLENS_ACCESS_KEY` in the root `.env` file, then run:

```sh
docker compose up --build
```

- Web UI: `http://localhost:3000`
- API: `http://localhost:8000` (interactive docs are disabled)
- Ollama: `http://localhost:11434`

Compose defaults to `EMBEDDING_PROVIDER=local`. Model downloads and uploaded
repositories persist in separate named volumes. Do not remove those volumes
when updating the app. The Compose file runs one backend container, matching
the single-process worker requirement.

## Public access

No public tunnel is currently active. The prior temporary Quick Tunnel hostname
expired, so there is no current public demo URL to use. Starting a new Quick
Tunnel creates a temporary hostname and exposes the shared owner workspace to
anyone who can reach it. Keep the host machine, frontend, backend, and tunnel
running for as long as the link should work. A restarted tunnel receives a new
hostname.

## Managed hosting

A managed deployment needs a hosting account and a configured backend address
at frontend build time. It also needs persistent storage for the SQLite
database, uploaded source files, and indexes. The deployment must preserve the
single-backend-process requirement and protect the shared owner workspace.

A remote backend cannot use Ollama running on a developer's localhost. Provision
a server-side model or configure a supported generation API. Without one, chat
uses the application's grounded offline fallback rather than model generation.

## Verification status

Compose configuration validation has passed. Container builds and remote
runtime checks have not run because no Docker daemon or hosting account/server
was available during the last deployment review.
