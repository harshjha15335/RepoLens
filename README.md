# RepoLens
### Codebase Intelligence & AI Studio

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.4+-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Tree--Sitter](https://img.shields.io/badge/Tree--Sitter-AST%20Chunking-1E293B)](https://tree-sitter.github.io)
[![FAISS](https://img.shields.io/badge/FAISS-Dense%20Retrieval-blue)](https://github.com/facebookresearch/faiss)
[![BM25](https://img.shields.io/badge/BM25-Lexical%20Ranking-orange)](https://en.wikipedia.org/wiki/Okapi_BM25)

**RepoLens** is an advanced codebase intelligence platform designed for exploring, visualizing, and tutoring on complex software repositories.

Unlike generic code search tools that treat source code as flat text, **RepoLens** parses repositories into Abstract Syntax Trees (ASTs) using Tree-sitter, models dependency and call graphs, and applies a multi-stage hybrid retrieval pipeline (Dense Vector + Lexical BM25 + Reciprocal Rank Fusion + 1-Hop Code Graph Expansion + MMR Diversity). Explanations are delivered across specialized tutor modes and grounded with line-accurate citations and an interactive visual knowledge graph.

---

## Key Capabilities

1. **AST-Aware Structural Ingestion**:
   - Ingests repositories via ZIP archive upload or Git clone URL with path traversal defenses (Zip-Slip protection, symlink sanitization).
   - Multi-language AST parsing (Python, JavaScript, TypeScript, Java, C, C++, Go) extracting classes, methods, functions, imports, and docstrings.
   - Small-to-big chunking preserves local AST node context alongside broader parent context.

2. **Advanced Multi-Strategy Hybrid Retrieval**:
   - **Dense Retrieval**: FAISS index using configurable embedding models (SentenceTransformers or deterministic local embeddings).
   - **Lexical BM25 Retrieval**: Custom code-aware tokenization splitting `camelCase`, `snake_case`, identifiers, and file paths.
   - **Reciprocal Rank Fusion (RRF)**: Merges lexical and dense rank scores without calibration sensitivity ($k=60$).
   - **Code Knowledge Graph Expansion**: 1-hop BFS traversing caller-callee, inheritance, and import relationships.
   - **Fast-Path Retrieval**: Bypasses heavy graph expansion when specific code ranges are already selected, achieving sub-second context retrieval.
   - **Maximal Marginal Relevance (MMR)**: Penalizes semantic redundancy to maximize diversity within token limits.

3. **Interactive Visual Code Knowledge Graph**:
   - **Force-Directed SVG Canvas**: Real-time spring simulation automatically arranges files, classes, and functions with anti-overlap collision physics.
   - **Directed Relationship Edges**: Interactive arrows with relationship badges (`CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`).
   - **Canvas Controls**: Full pan and zoom (wheel, toolbar controls, auto-fit centering), node dragging with dynamic edge tracking, and double-click to inspect code in the viewer.
   - **Collapsible Inspector**: Slide-over details panel displaying qualified names, file coordinates, and connected neighbor dependencies.
   - **View Toggles**: Switch seamlessly between Interactive Graph, Card Explorer, and Static Call Flow traces.

4. **Specialized Tutor Modes**:
   - **Beginner**: Concept & Analogy, Step-by-Step Breakdown, Jargon Buster.
   - **Developer**: Architecture & Data Flow, Implementation & Abstractions, Engineering Notes.
   - **Interview**: The 30-Second Elevator Pitch, Design Trade-offs & Decisions, Time & Space Complexity (Big-O), Top Interview Questions.
   - **Debug**: Edge Cases & Failure Points, State Mutation & Invariants, Defensive Fixes & Tests to Add.

5. **Multi-Provider LLM Generation**:
   - Unified support for OpenRouter (`openai/gpt-4o-mini`, `openai/gpt-oss-20b`), Groq, OpenAI, and Ollama.
   - Grounded offline fallback synthesis when external LLM providers are unreachable.
   - Sub-5s response latency with fast-path retrieval and optimized prompt pipelines.

6. **Interactive Code & Citation Inspector**:
   - Every factual claim links directly to `[file_path:start_line-end_line]`.
   - Clicking a citation opens the interactive Code Viewer tab and smoothly scrolls to and highlights target lines.
   - In-IDE code editing with line numbers, status indicators, and re-indexing.
   - Collapsible Retrieval Transparency panel exposing detected Query Intent, Strategy, Latency (ms), and Chunk Relevance Scores.

7. **Built-in Retrieval Benchmarks & Evaluation Suite**:
   - Quantitative evaluation framework measuring Recall@5, Recall@10, Mean Reciprocal Rank (MRR), and Latency against curated codebase ground-truth datasets.
   - Real-time comparison across BM25, Dense, Hybrid RRF, and Graph Expansion.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |             Next.js 16 UI             |
                      |  (Header, File Tree, Symbols, Chat,   |
                      |   CodeViewer, Knowledge Graph, Eval)  |
                      +-------------------+-------------------+
                                          | REST / JSON
                                          v
                      +---------------------------------------+
                      |         FastAPI Application           |
                      |      (/repositories, /chat,           |
                      |       /retrieval, /evaluation)        |
                      +-------------------+-------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
        v                                 v                                 v
+-------------------+             +-------------------+             +-------------------+
| Ingestion & AST   |             | Hybrid Retrieval  |             | Tutor Generation  |
| - Zip / Git Ingest|             | - FAISS Dense     |             | - Mode Templates  |
| - Tree-sitter AST |             | - Lexical BM25    |             | - Small-to-Big    |
| - Code Graph Build|             | - RRF Fusion      |             | - Citation Parser |
| - SQLite Metadata |             | - Graph 1-Hop BFS |             | - Multi-Provider  |
+-------------------+             | - MMR Reranking   |             +-------------------+
                                  +-------------------+
```

---

## Repository Structure

```
RepoLens/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routers (chat, repositories, retrieval, eval)
│   │   ├── core/            # Config, database, security middleware, logging
│   │   ├── models/          # SQLAlchemy async models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Ingestion, Parser, Graph, Retrieval, Generation, Eval
│   │   └── utils/           # Path security, language detection, tokenizers
│   ├── tests/               # Backend unit and integration tests
│   ├── Dockerfile           # Python 3.12 slim container definition
│   └── pyproject.toml       # Backend dependencies and tools
├── frontend/
│   ├── app/
│   │   ├── components/      # Header, Sidebar, ChatPanel, CodeViewer, GraphView
│   │   ├── lib/             # Typed API client library
│   │   ├── types/           # TypeScript data models
│   │   ├── globals.css      # Dark mode tokens & glassmorphism utilities
│   │   ├── layout.tsx       # Root layout & typography
│   │   └── page.tsx         # Main interactive split-view workspace
│   ├── Dockerfile           # Multi-stage production container
│   └── package.json         # Next.js 16, React 19, Tailwind v4, Lucide
├── sample-repos/
│   └── calculator/          # Sample multi-module AST & inheritance demo repo
├── evaluation/
│   └── datasets/            # Ground-truth evaluation benchmarks
├── docs/                    # Architecture, retrieval, security, evaluation docs
├── scripts/
│   ├── seed_demo.py         # 1-click seeding & demo generation
│   └── run_benchmarks.py    # Offline evaluation runner
└── docker-compose.yml       # Complete multi-container deployment
```

---

## Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 20+** and **npm 10+**
- *(Optional)* **Docker & Docker Compose**

---

### Local Development Setup

#### 1. Configure Environment

Copy `.env.example` to `backend/.env` and configure your settings:

```bash
# Windows (PowerShell):
Copy-Item .env.example backend/.env

# Linux / macOS:
cp .env.example backend/.env
```

Ensure `REPOLENS_ACCESS_KEY` is set to a secret string of at least 32 characters.

To use cloud LLM providers (e.g. OpenRouter, Groq, or OpenAI):
```env
LLM_PROVIDER=openrouter
LLM_MODEL=openai/gpt-4o-mini
LLM_API_KEY=sk-or-v1-your-api-key
```

#### 2. Start the Backend

```bash
cd backend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -e .
uvicorn app.main:app --reload --port 8000
```
Backend will be live at `http://localhost:8000`.

#### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```
Frontend will be live at `http://localhost:3000`. Sign in with your configured `REPOLENS_ACCESS_KEY`.

#### 4. Seed Sample Demo Data

In a separate terminal, run:
```bash
python scripts/seed_demo.py
```
This automatically uploads `sample-repos/calculator.zip`, triggers Tree-sitter AST parsing, builds the code graph and FAISS vector index, and creates sample conversations.

---

### Docker Compose

To run the complete production stack (Backend + Frontend + Ollama) in Docker:

```bash
docker compose up --build
```

- Web UI: `http://localhost:3000`
- API: `http://localhost:8000`
- Ollama: `http://localhost:11434`

---

## Testing & CI

### Backend Tests & Linting

```bash
cd backend
python -m pytest tests -v
python -m ruff check app tests
```

### Frontend Tests, Type-Check & Linting

```bash
cd frontend
node --test tests/api-errors.test.mjs
npx tsc --noEmit --incremental false
npm run lint
npm run build
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Healthcheck and indexer status |
| `POST` | `/api/repositories/upload` | Upload ZIP repository archive |
| `POST` | `/api/repositories/git` | Clone & index Git repository by URL |
| `GET` | `/api/repositories` | List all indexed repositories |
| `GET` | `/api/repositories/{id}/status` | Get real-time indexing stage & progress |
| `GET` | `/api/repositories/{id}/files` | List repository source files |
| `GET` | `/api/repositories/{id}/files/content` | Read source file content |
| `PUT` | `/api/repositories/{id}/files/content` | Update file content and trigger re-index |
| `GET` | `/api/repositories/{id}/symbols` | List extracted AST symbols (classes, functions) |
| `GET` | `/api/repositories/{id}/graph` | Retrieve node-and-edge knowledge graph |
| `GET` | `/api/repositories/{id}/call-flows` | Retrieve caller-callee hierarchy traces |
| `POST` | `/api/chat` | Send question to AI Tutor with selected mode |
| `GET` | `/api/sessions` | List chat sessions |
| `GET` | `/api/sessions/{id}` | Get session details & message history |
| `POST` | `/api/retrieval/search` | Direct search against FAISS/BM25/Graph |
| `POST` | `/api/evaluation/run` | Run benchmark suite comparing retrieval strategies |
| `GET` | `/api/evaluation/{id}` | Get benchmark results (Recall@K, MRR, Latency) |

---

## Security

- **Path Traversal Defenses**: Rejects paths containing `..`, absolute paths, or symbolic links resolving outside the repository root.
- **Archive Size & File Limits**: Prevents zip bombs with a configurable upload cap (50 MB by default), per-file limits, and extraction byte limits.
- **Citation Grounding**: AI Tutor responses are strictly cross-referenced against retrieved chunk coordinates to prevent hallucinated line references.
- **Session Authentication**: Token-based security middleware securing all endpoints via `REPOLENS_ACCESS_KEY`.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
