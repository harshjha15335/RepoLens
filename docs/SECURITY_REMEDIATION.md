# RepoLens audit remediation — 12 October 2026

This records what was changed in response to the repository audit and what the
current checks actually prove. RepoLens is a **single-owner workspace**. Everyone
who signs in with the owner key sees the same repositories and chat sessions.

## Implemented

- Owner access: a 32+ character `REPOLENS_ACCESS_KEY` is required at startup.
  Browser sign-in issues an HTTP-only, same-site session cookie; native clients
  can use a bearer key. Repository, file, chat, retrieval, evaluation, graph and
  upload endpoints require authentication. Cross-site mutations are rejected,
  sessions expire, and sign-out revokes the cookie. API documentation endpoints
  are disabled. This is one-process authentication, not user accounts.
- Resource controls: requests and expensive work have per-process rate and
  concurrency caps. Request bodies and ZIP extraction are bounded; the default
  upload limit is 50 MB. File extraction and deletion use resolved containment
  checks. Git imports allow only public HTTPS repositories from GitHub, GitLab,
  or Bitbucket; the worker rechecks the destination and restricts Git transports.
- Index safety and accuracy: BM25 indexes use validated JSON instead of Python
  pickle. Dense indexes record the actual embedding provider, model, dimension
  and fingerprint, and refuse mismatched or legacy vectors with a reindex
  message. The explicit graph-expansion retrieval strategy now performs graph
  expansion. Sentence Transformer models load from local cache only; an
  unavailable model falls back to deterministic local embeddings.
- Jobs and errors: startup marks interrupted indexing and evaluation jobs
  failed so that they can be retried. Unsupported chat streaming requests fail
  validation instead of silently returning a non-streaming response. Reindex
  and retrieval failures expose actionable API errors.
- Deployment and checks: Docker includes the sample ZIP and evaluation dataset,
  uses a persistent absolute database path, and requires the owner key. GitHub
  Actions runs backend tests and Ruff plus frontend API tests, TypeScript,
  ESLint and a production build. The sample-upload route enforces sign-in.

## Verification on Windows

- Backend: 138 tests passed, 3 skipped; Ruff passed. The skips include a native
  symlink case unavailable without Windows symlink privilege; a mocked
  containment regression still runs. GitHub Actions on Linux passed all 141
  backend tests and Ruff on commit `91e176c`.
- Frontend: 12 API tests passed; TypeScript and the Next.js 16.4.0 production
  build passed. The production dependency scan reported zero vulnerabilities.
  ESLint passed with zero errors and warnings after unused-code cleanup. The
  GitHub Actions frontend job also passed on commit `91e176c`.
- Runtime: all three existing calculator repositories were reindexed and
  reached `READY`. BM25, dense, hybrid and graph-expanded retrieval returned
  results. The production frontend proxy returned 401 for anonymous repository
  and sample requests, 403 for a cross-site sample request, and 200 for owner
  sign-in and authenticated repository access. Sign-out returned subsequent
  requests to 401. An authenticated sample upload indexed successfully and
  the test-created repository was removed afterward. File, symbol, graph and
  call-flow endpoints returned 200. A four-strategy evaluation completed, and
  a real local Ollama chat request returned an answer with one citation in
  85.5 seconds.
- `docker compose config --quiet` passed with a test key. A Docker image build
  could not be run because Docker Desktop's Linux engine was unavailable.
- `pip-audit` found no known vulnerabilities in the locally installed Python
  packages after updating setuptools. Its PyPI scan cannot assess the installed
  CPU PyTorch wheel. The frontend's full development-dependency audit still
  reports a transitive `braces` advisory without a compatible automatic fix.

## Remaining limits

- Background tasks and login/rate state live in one process. A restart records
  failure; it does not resume work. A durable queue and independent workers are
  still needed for reliable scaled hosting. DNS checks reduce Git import risk,
  but production network egress controls are also needed against DNS rebinding.
- Local CPU generation can take roughly a minute. Streaming responses are not
  implemented. Citation coordinates do not prove every generated claim;
  interview scoring is heuristic. Graph queries retain the 500-node cap and do
  not offer pagination. The small calculator benchmark does not establish
  general retrieval accuracy.
- Docker images still need their first build on a host with Docker. No public
  Cloudflare tunnel is currently active; prior temporary hostnames expired.
  Public availability has not been re-established.
- The repository metadata names an MIT license, but there is no root LICENSE
  file. A copyright holder must confirm the intended grant before one is added.
