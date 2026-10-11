# RepoLens Windows audit

Audited on 11–12 October 2026 in `C:\Users\ranja\RepoLens`, branch
`codex/fix-indexing-start`. This is the checkout running the local services.
Changes are local and uncommitted.

## Findings and fixes

| Area | Finding | Result |
| --- | --- | --- |
| Workspace | Tutor-width slider, desktop Explorer/AI tutor buttons and command-search hint cluttered the workspace. | Removed requested controls; mobile Files/Code/Chat navigation remains available. |
| Knowledge graph | Toolbar squeezed headings and filters; inspector could overflow smaller workspace panes. | Wrapping toolbar, responsive inspector layout and scrollable panels. |
| Navigation | Graph and interview views lacked an obvious return route. | Explicit Back to code buttons; file, symbol and citation selections return to source. |
| Graph relationships | Inspector displayed indistinguishable relationship types and silently limited them to eight. | Every available relationship includes its connected symbol; clicking it selects that node. |
| Graph requests | Changing filters could allow an older response to overwrite a newer graph. | Ignore obsolete responses; preserve selection only when it belongs to the returned graph; display API errors. |
| Subtitles | Decorative feature explanations appeared throughout dialogs and workspace panels. | Removed those subtitles from welcome, upload, tutor, interview, retrieval, evaluation and call-flow screens. Required form labels, errors and empty-state guidance remain. |
| Reindex | New indexed-file/chunk records accumulated beside old ones, breaking single-file lookups. | Replace previous chunks and files before storing the new index; stable chunk ordering for FAISS. Both existing calculator repositories were reindexed successfully. |
| Git reindex | The selected branch was not retained; an existing checkout could stay stale. | Persist branch metadata, fetch the selected branch and reset the managed clone to its fetched head. Reject unsafe branch arguments and paths outside managed storage. |
| Benchmarks | Worker could start before its evaluation row was committed; dataset path and strategy mappings were incorrect. | Commit before dispatch, resolve datasets from repository root, use actual dense/BM25/hybrid/graph strategies, return separate metrics and visible failures. |
| Benchmark UI | Overlapping polls and missing terminal handling left a running state onscreen. | One poll at a time, cleanup on close/repository change, visible failure/timeout state and reset on repository change. |
| Parsing | TypeScript and TSX did not use their appropriate tree-sitter grammars. | Load both grammars; verify class/function extraction. |
| Static graph | Class bodies produced fabricated callers and methods could resolve to the wrong class. | Restrict calls to actual function/method bodies, resolve self methods within their class and omit ambiguous global matches. |
| Offline chat | Fallback answers asserted calculator behavior without sufficient evidence. | Show actual retrieved excerpts with valid citations and state when the language model is unavailable. |
| Chat isolation | A session from a different repository could be used in a request. | Reject cross-repository sessions and persist the requested tutor mode. |
| Chat controls | Several menu actions were placeholders. | Working New Chat, Start Interview, recent-chat selection and deletion. |
| Interview questions | Focus/difficulty were ineffective; split chunk names and inferred inheritance leaked into questions. | Validate inputs, use real symbols and INHERITS edges, clean split names, honor selected focus and difficulty. |
| Interview feedback | Keyword scoring was presented as correctness grading; citations could target unrelated imports. | Label source overlap honestly and prefer the question's actual target file/symbol chunks. |
| Repository switching | Prior tabs/chat could survive switching repositories; delayed responses could restore obsolete data. | Reset workspace context, ignore obsolete repository loads and use request versions to discard stale file results. |
| Settings | Several tabs showed hardcoded provider/retrieval/privacy options. | Retain working font-size and tutor-mode controls; remove placeholder settings and theme command. |
| File access | Prefix-based containment checks did not reliably enforce the repository boundary. | Resolve paths, require containment and an indexed-file record. |
| Deletion | SQLite foreign keys were not enabled; deleted data could survive, and an immediate GET could race the commit. | Enable foreign keys, cascade graph/evaluation records and commit deletion before returning. Check managed storage boundaries before filesystem cleanup. |
| Packaging | Invalid build backend prevented ordinary package builds. | Use setuptools.build_meta, document backend usage and verify a wheel build. |
| Code quality | Explicit any types and effect state updates failed lint. | Replace types, defer initial requests safely and use precise effect dependencies. |

## Verification

| Check | Result |
| --- | --- |
| Backend pytest suite | 50 passed, including indexing transactions, evaluation dispatch, Git branch refresh, reindex replacement, graph resolution, parsing, grounded fallback, deletion and target-source interview feedback. |
| Backend Ruff | No errors. |
| Frontend API error regressions | 8 passed: JSON, plain text, HTML proxy, empty/null errors and successful responses. |
| TypeScript | `npx tsc --noEmit --incremental false` passed. |
| Frontend production build | `npm run build` passed; frontend stopped during build and restarted afterward. |
| Frontend ESLint | No errors. Remaining warnings are unused imports/variables and unused expressions; no hook-dependency warnings remain. |
| Working-tree whitespace | `git diff --check` passed. Git reports Windows line-ending normalization notices. |
| Live API smoke audit | 55 of 55 checks passed through the frontend proxy. Raw results: [runtime-results.json](runtime-results.json). |
| Final interview API check | Calculator architecture feedback cites `src\calculator.py:L4-59`, rather than unrelated import excerpts. |

The live audit exercised both existing calculator repositories plus disposable
Python/TypeScript/TSX ZIP and Git fixtures. It checked repeated reindexing without
duplicate records, source reads, symbols, graph endpoints and call resolution,
all four retrieval strategies, all four tutor modes, session persistence,
cross-repository session rejection, interview inputs and feedback, benchmark
completion with four strategy rows, traversal rejection, unsafe ZIP rejection,
selected non-default Git branch import/reindex and immediate deletion visibility.
All disposable audit repositories were removed; both calculator repositories
remain READY with four files and 42 chunks each.

Browser checks covered desktop and narrow/mobile workspace layouts, graph and
call-flow navigation, graph relationship selection, Back to code, source opening
from citations and retrieval results, chat sending and saved-chat restoration,
interview setup/feedback, benchmark results and font-size adjustment. The saved
[graph screenshot](graph.jpg) shows the corrected workspace and return control.

## What the controls do

The `</>` button opens the code viewer. The Coding button opens the same source
view; neither runs the uploaded code.

Tutor mode changes the prompt used for **future chat responses**:

| Mode | Intended response framing |
| --- | --- |
| Beginner | Simple explanations, defined terms and step-by-step control flow. |
| Developer | Implementation, architecture, APIs, data flow and design decisions. |
| Interview | Tradeoffs, complexity and likely interview discussion topics. |
| Debug | Execution paths, callers/callees, state changes and error propagation. |

Mode selection does not reindex the repository, change the embeddings or rerun
previous messages. Interview chat mode and the separate question/answer Interview
screen are distinct features.

## Practical limits

- The current runtime uses deterministic local token/ngram embeddings, not a
  transformer model. Retrieval relevance can vary; passing retrieval checks does
  not establish semantic accuracy for every query or repository.
- The original audit exercised offline excerpts. Follow-up investigation found
  Ollama running with `qwen2.5-coder:latest`, while RepoLens requested the missing
  `llama3.1:8b` model. Local backend configuration now selects the installed model.
  No model download or remote API is required.
- Interview scores measure source-term overlap, not reasoning correctness.
- Graphs and call flows are static approximations. Dynamic dispatch, unresolved
  external dependencies and ambiguous calls are not guaranteed to be represented.
- The evaluation uses a small ground-truth dataset; its results are a diagnostic
  comparison, not evidence of general retrieval quality.
- ESLint still reports existing unused-code warnings. Next.js reports that a
  separate user-folder package-lock is outside this checkout and is ignored; the
  production build succeeds.
- These checks cover representative runtime paths and supported local fixtures,
  not every possible uploaded language, archive size or concurrent workload.

## Repeating the main checks

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/ -q
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests
cd frontend
node --test tests/api-errors.test.mjs
npx tsc --noEmit --incremental false
npm run lint
# Stop the dev server before this command, then restart it afterward:
npm run build
```

## Selected-code follow-up (12 October)

Clicking Explain, Debug or Trace collapsed the browser selection. The viewer's
mouseup handler removed the toolbar before the button click could execute.
The toolbar now preserves selection while clicked and stops that mouseup from
reaching the selection handler. Line coordinates come from rendered source-line
elements instead of searching for a potentially repeated text fragment.

The frontend sends structured `code_context` with file and line coordinates.
The API verifies the indexed file and reads the actual selected source; it ignores
client-supplied text as evidence. That source takes priority in prompts, fallback
excerpts and citation validation. Debug and Trace use debug framing. On mobile,
selection actions open the chat panel. Buttons are disabled while a response is
pending or the repository is not ready.

The same investigation found an impractical two-second Ollama response timeout
and Next.js's default 30-second proxy timeout. Model responses now allow 120
seconds with a three-second connection timeout; the frontend proxy allows 150
seconds. Local context/output limits are set to 512/128 tokens to reduce CPU
generation time. These are local `.env` settings, not a change to provider defaults.

Follow-up checks: 54 backend tests passed, including four selected-code tests;
Ruff passed; TypeScript and all eight API regression tests passed; full ESLint
reported zero errors and 47 warnings. Browser reproduction confirmed the original
lost-click behavior and the repaired action sends the selected file/line range.

Live model verification returned actual selected-source answers for Explain and
Debug, with `selected_code=true` and no offline fallback. Their generation times
were approximately 87 and 72 seconds on the CPU. Response prompts now request a
complete concise answer within the configured output budget. Message mode badges
use each response's actual mode, and saved-session responses retain retrieval
metadata so those badges and the retrieval inspector survive reloads.

Each selected-code request now records an explicit `explain`, `debug` or `trace`
action. These focused requests omit prior chat history and supply numbered source
lines, avoiding stale explanations and giving the model exact citation positions.

The final live Trace request returned a complete answer stating that the selected
initializer contains no direct calls, with a citation to its actual lines 7-9.
All three toolbar actions were exercised in the browser and returned real model
answers. Screenshot: [selection-actions.jpg](selection-actions.jpg).

## CPU generation wait follow-up (12 October)

The user's selected import-lines request completed in 95.57 seconds: retrieval
used 48.61 ms and model generation used 95,525.09 ms. Ollama reports the installed
qwen2.5-coder:latest model as 7.6B, with about 5 GB resident and no GPU memory.
Windows had approximately 470 MB free physical memory during investigation.
The request was running, not blocked by indexing or retrieval. Model output can
still be truncated at the local 128-token limit; increasing that limit would
increase latency further. A smaller local model was proposed, but its download
has not been authorized. Current latency remains a material limitation.

The frontend now limits API waits to 30 seconds (160 seconds for chat), cleans up
its timers, and distinguishes a client deadline from cancellation of server work.
The loading indicator displays elapsed seconds and changes its message after 20
seconds. Session-list refresh no longer keeps generation loading active after an
answer. The follow-up composer blocks submission while generating and includes
verified selected-source context when applicable. Generic server errors include
an actionable explanation. A follow-up request during the backend restart hit
Next.js ECONNREFUSED; the backend was restarted successfully and proxied health
checks passed afterward. Default-configuration tests now ignore the developer's
.env and environment overrides so local embedding settings do not invalidate them.
