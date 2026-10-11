# Public deployment audit — 12 October 2026

Checkout: `C:\Users\ranja\RepoLens`, branch `codex/fix-indexing-start`.
Public URL: https://computers-welfare-anytime-stem.trycloudflare.com/

The audit covers the Windows backend, optimized Next.js frontend, and requests
through the public Cloudflare tunnel. Existing edits were preserved. The frontend
production build is served from `.next-audit`; the backend uses production logging
and local token/ngram embeddings. Repository data and Ollama remain on this PC.

## Issues found and fixed

- Chat flushed its user message before awaiting model generation. SQLite held
  its sole writer lock throughout generation; a simultaneous public ZIP upload
  returned HTTP 500 with `database is locked`. Chat now materializes history and
  releases its read transaction, generates the answer, then saves the successful
  exchange in one short transaction. Failed generation saves neither message.
  An existing session is revalidated after generation in case it was deleted.
- Reindex now distinguishes an active in-process job from an orphaned persisted
  PENDING job after restart. Queue reservations are released even on failures.
- Explicit graph retrieval expands connected chunks for all intents and includes
  bounded neighbor results in the returned top-k rather than truncating them away.
- Frontend request versions prevent stale file, session, repository and chat
  responses from replacing the current view. Duplicate chat submission is guarded;
  unsuccessful submissions preserve the composer draft.
- Mobile code attachment opens the correctly named tutor panel. Clipboard success
  follows the actual write; Windows downloads use a proper basename. Modal close
  controls have labels, repeated interview excerpt headings are removed, and
  retrieval/evaluation modals have distinct React keys.
- ESLint excludes the isolated production output so generated bundles are not
  mistaken for application source.

Earlier selection toolbar, graph navigation/layout, timeout, API-error and subtitle
fixes are documented in [AUDIT.md](AUDIT.md). They remain in this checkout.

## Verification

| Check | Result |
| --- | --- |
| Backend full pytest suite | 60 passed |
| Backend Ruff, app and tests | Passed |
| Frontend API regression tests | 12 passed |
| TypeScript, incremental disabled | Passed |
| ESLint | 0 errors; 46 existing warnings |
| Optimized Next.js production build | Passed and serving publicly |
| Git whitespace check | Passed; Windows line-ending notices only |
| Public API probe | 14/14 passed |
| Disposable public ZIP workflow | 8/8 passed |
| Real-model concurrent chat workflow | 3/3 passed |
| Compose configuration | Passed; container build not exercised |

The public API probe checked health, READY status, indexed files/source,
graph integrity, call flows, all four retrieval strategies, interview questions
and feedback, completed evaluation results, and rejection of escaping source paths.

The disposable workflow uploaded three Python/TypeScript/README files, reached
READY, retrieved their source, reindexed the ZIP, confirmed stable file/chunk
counts, and deleted only the repository it created. It was repeated while a real
Debug chat generated: upload and reindex finished in 7.44 seconds before chat
completed. Chat returned a grounded constructor answer with lines 7–9 citations,
`selected_code=true`, and an atomically persisted two-message exchange. Generation
took 56.33 seconds; retrieval took 24 ms. Its temporary chat session was removed.
Four regression cases use a real separate SQLite writer during generation and
cover new/existing sessions and successful/failed generation.

## Browser coverage

Desktop and 390×844 mobile checks exercised graph node/type/relationship filtering,
inheritance inspection, source navigation, graph back navigation, tutor modes,
font settings, interview start/answer/feedback/next/back, hybrid and BM25 retrieval,
retrieval-to-code navigation, new chat, and Windows file download. Mobile selecting
constructor lines 7–9 and pressing Explain opened Chat with the exact attachment.
Switching repositories during generation cleared its pending UI; its eventual
answer did not appear in the other repository. Returning to the original saved
chat showed the correctly grounded explanation and source chips.

Explain, Debug and Trace returned real model answers during the earlier selected
code audit. This pass repeated mobile Explain and public Debug with concurrent
writes. Existing saved messages can still contain responses from older code/model
configuration; fixes do not rewrite chat history.

Fresh browser evaluation completed all four strategies over 12 queries:

| Strategy | Recall@5 | Recall@10 | MRR | Mean retrieval latency |
| --- | --- | --- | --- | --- |
| BM25 | 56.3% | 72.5% | 0.783 | 12.2 ms |
| Dense | 49.2% | 70.0% | 0.729 | 12.4 ms |
| Hybrid RRF | 54.6% | 72.3% | 0.781 | 13.3 ms |
| Graph expansion | 54.6% | 75.6% | 0.785 | 26.4 ms |

See [benchmark screenshot](public-evaluation.jpg),
[public API results](public-api-results.json),
[ZIP workflow results](public-mutation-results.json), and
[concurrent chat results](public-chat-results.json).

## Remaining limits

- CPU-only 7.6B Ollama generation remains slow: observed answers took roughly
  56–96 seconds. The local 128-token output limit can truncate longer answers.
  A smaller model download has not been authorized. This pass does not claim
  chat latency is solved.
- The tunnel is temporary and needs this PC, internet, frontend, backend and
  tunnel process running. Public shared repositories/chat access was explicitly
  authorized; there is no per-user access control.
- Docker images were not built because the local daemon is unavailable. Git
  reindex is covered by integration fixtures; this pass did not import a fresh
  external Git repository through the public UI.
- Clipboard handling was checked in code and browser actions, but the native
  Windows clipboard payload was not conclusively verified through the browser.
- ESLint warnings remain mostly unused imports/parameters. Static graphs,
  deterministic embeddings, overlap-based interview scoring and the small
  benchmark dataset have the accuracy limits described in the earlier audit.
- Representative feature paths passed; arbitrary archive sizes/languages and
  production-scale concurrent workloads were not exhaustively tested.
