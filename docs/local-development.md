# Develop RepoLens on Windows

Use one checkout for both Codex and your terminals. If your working checkout is
`C:\Users\ranja\RepoLens`, open that exact folder as a local Codex project.
Another folder named RepoLens may contain a different branch and dependencies.

## Get the cloud changes

From your project folder, preserve any local edits, then run:

```powershell
git fetch origin
git switch codex/fix-indexing-start
git pull --ff-only
```

This branch includes indexing transaction fixes, ZIP reindexing, API error
handling, and the updated welcome screen and responsive workspace. Cloud
processes and Linux dependencies do not transfer to Windows.

## Install dependencies if needed

Prerequisites: Python 3.11 or newer, Node.js 20.9 or newer, and npm. From the
repository root, create a Windows virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -c "import pathlib, subprocess, sys, tomllib; p = tomllib.loads(pathlib.Path('backend/pyproject.toml').read_text())['project']; subprocess.run([sys.executable, '-m', 'pip', 'install', *p['dependencies'], *p['optional-dependencies']['dev']], check=True)"
cd frontend
npm ci
cd ..
```

The backend runs from source. Its current packaging backend is invalid, so
`pip install -e .` is not used. No FastAPI downgrade is required with this branch.

## Start both services

Stop any previous backend/frontend instances with Ctrl+C in their terminals.
Keep the following two terminals open.

Backend, starting from the repository root:

```powershell
$env:EMBEDDING_PROVIDER = "local"
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend, starting from the repository root in a second terminal:

```powershell
cd frontend
npm run dev
```

Open http://localhost:3000 in your browser or the Codex browser panel.
Local embeddings use deterministic token/ngram vectors without model downloads;
they are not transformer embeddings. Chat can use the application's offline
grounded synthesis when Ollama is absent. If changing the embedding provider,
reindex repositories so document and query vectors use the same provider.

## Check readiness and recover a pending upload

In a third PowerShell window:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
$repos = (Invoke-RestMethod http://localhost:8000/api/repositories).repositories
$repos | Format-Table id, name, status, progress
```

The health response verifies API reachability, not that indexing completed. A
repository must reach `READY`. Restarting the backend does not automatically
resume old jobs. For a `PENDING` or `FAILED` calculator upload:

```powershell
$repo = $repos | Where-Object name -eq "calculator" | Select-Object -First 1
if ($repo -and $repo.status -in @("PENDING", "FAILED")) {
    Invoke-RestMethod -Method Post "http://localhost:8000/api/repositories/$($repo.id)/index"
    Invoke-RestMethod "http://localhost:8000/api/repositories/$($repo.id)/status" |
        Format-List status, progress, progress_message, error_message
}
```

The POST response reports the queued state; query status again to see the worker's
result. If progress stays at zero, inspect the Uvicorn terminal traceback rather
than repeatedly retrying. If the browser reports a proxy error but the API health
check works, inspect the terminal running Next.js and any local `.env` overrides
for `NEXT_PUBLIC_BACKEND_URL` or `NEXT_PUBLIC_API_URL`.

## Validation

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/ -q
```

From `frontend`:

```powershell
node --test tests/api-errors.test.mjs
npx tsc --noEmit --incremental false
```

Stop the frontend dev server before running `npm run build`; restart it afterward.
Cloud validation passed 40 backend tests, 8 API-client regression tests, frontend
build/type checks, sample indexing and retrieval, chat citations, and desktop/mobile
UI interactions. Repeat checks locally when debugging Windows-specific behavior.
