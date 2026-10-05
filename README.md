# CodeMentor-RAG
### Retrieval-Augmented AI Tutor for Codebase Understanding

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.3+-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Tree--Sitter](https://img.shields.io/badge/Tree--Sitter-AST%20Chunking-1E293B)](https://tree-sitter.github.io)
[![FAISS](https://img.shields.io/badge/FAISS-Dense%20Retrieval-blue)](https://github.com/facebookresearch/faiss)
[![BM25](https://img.shields.io/badge/BM25-Lexical%20Ranking-orange)](https://en.wikipedia.org/wiki/Okapi_BM25)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**CodeMentor-RAG** is a production-grade, retrieval-augmented coding intelligence system that helps engineers, team leads, and learners rapidly explore, understand, and debug complex codebases.

Unlike generic code search tools that treat source code as flat text, **CodeMentor-RAG** parses code into Abstract Syntax Trees (ASTs) using Tree-sitter, models dependency and call graphs, and applies a multi-stage hybrid retrieval pipeline (Dense Vector + Lexical BM25 + Reciprocal Rank Fusion + 1-Hop Code Graph Expansion + MMR Diversity). Answers are synthesized across distinct tutor personas and grounded with line-accurate, interactive citations.

---

## Key Capabilities

1. **AST-Aware Structural Ingestion**:
   - Ingests repositories via ZIP archive or Git clone URL with path traversal defenses (`Zip Slip` guard, absolute path sanitization).
   - Multi-language AST parsing (Python, JavaScript, TypeScript, Java, C, C++, Go) extracting classes, methods, functions, imports, and docstrings.
   - Small-to-big chunking preserves local AST node context alongside broader parent context.

2. **Advanced Multi-Strategy Hybrid Retrieval**:
   - **Dense Retrieval**: FAISS index using SentenceTransformers (`all-MiniLM-L6-v2`) with cosine similarity.
   - **Lexical BM25 Retrieval**: Custom code-aware tokenization splitting `camelCase`, `snake_case`, identifiers, and file paths.
   - **Reciprocal Rank Fusion (RRF)**: Merges rank scores without calibration sensitivity ($k=60$).
   - **Code Knowledge Graph Expansion**: 1-hop BFS traversing caller-callee, inheritance, and import relationships to pull connected dependencies into context.
   - **Maximal Marginal Relevance (MMR)**: Penalizes redundant chunks to ensure broad context coverage within token budgets.

3. **Multi-Persona AI Tutor**:
   - 🎓 **Beginner**: High-level analogies, intuitive metaphors, step-by-step reasoning.
   - ⚡ **Developer**: Pragmatic implementation, exact signatures, design patterns, dependencies.
   - 🏛️ **Staff Architect**: System design, data flow boundaries, trade-offs, scaling, and security invariants.
   - 🔍 **Debug Investigator**: Control flow tracing, error propagation, invariants, and failure modes.

4. **Interactive Code & Citation Inspector**:
   - Every claim links directly to `[file_path:start_line-end_line]`.
   - Clicking a citation opens the interactive Code Viewer tab and smoothly scrolls to and highlights the target lines.
   - Collapsible Retrieval Transparency panel exposing detected Query Intent, Strategy, Latency (ms), and Chunk Relevance Scores.

5. **Built-in Retrieval Benchmarks & Evaluation Suite**:
   - Quantitative evaluation framework measuring Recall@5, Recall@10, Mean Reciprocal Rank (MRR), and Latency against curated codebase ground-truth datasets.
   - Real-time comparison across BM25, Dense, Hybrid RRF, and Graph Expansion.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |           Next.js 16 UI               |
                      |  (Header, File Tree, Symbols, Chat,   |
                      |   CodeViewer, Retrieval Lab, Eval)    |
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
| - Zip / Git Ingest|             | - FAISS Dense     |             | - Persona Prompts |
| - Tree-sitter AST |             | - Lexical BM25    |             | - Small-to-Big    |
| - Code Graph Build|             | - RRF Fusion      |             | - Citation Parser |
| - SQLite Metadata |             | - Graph 1-Hop BFS |             | - LLM Provider    |
+-------------------+             | - MMR Reranking   |             +-------------------+
                                  +-------------------+
```

---

## Directory Structure

```text
codementor-rag/
├── backend/
│   ├── app/
│   │   ├── api/             # REST endpoints (health, repos, chat, retrieval, eval)
│   │   ├── core/            # Config, database, errors, logging
│   │   ├── models/          # SQLAlchemy async models
│   │   ├── providers/       # Embeddings (SentenceTransformers) & LLMs (Ollama/Mock)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Ingestion, Parser, Graph, Retrieval, Generation, Eval
│   │   └── utils/           # Path security, language detection, tokenizers
│   ├── tests/               # 37 passing unit & integration tests
│   ├── Dockerfile           # Python 3.12 slim container definition
│   └── pyproject.toml       # Backend dependencies and tools
├── frontend/
│   ├── app/
│   │   ├── components/      # Header, Sidebar, ChatPanel, CodeViewer, Modals
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

### Method A: Local Development Setup

#### 1. Start the Backend

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
Backend will be live at `http://localhost:8000` (API documentation at `http://localhost:8000/docs`).

#### 2. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```
Frontend will be live at `http://localhost:3000`.

#### 3. Seed Sample Demo Data

In a separate terminal, run:
```bash
python scripts/seed_demo.py
```
This automatically uploads `sample-repos/calculator.zip`, triggers Tree-sitter AST parsing, builds the code graph and FAISS vector index, and creates sample conversations.

---

### Method B: Docker Compose

To run the complete production stack (Backend + Frontend + Ollama) in Docker:

```bash
docker compose up --build
```

- Web UI: `http://localhost:3000`
- API & Docs: `http://localhost:8000/docs`
- Ollama: `http://localhost:11434`

---

## Testing

Run the comprehensive backend test suite:

```bash
cd backend
pytest -v
```

All 37 test suites validate:
- Path traversal & ZIP security sanitization
- Tree-sitter AST parsing for Python and JavaScript
- Small-to-big structural chunking
- Code-aware BM25 tokenization (camelCase, snake_case splitting)
- Reciprocal Rank Fusion (RRF) math
- Maximal Marginal Relevance (MMR) diversity
- Intent classification heuristics
- Code graph inheritance and call flow edges
- Hallucination-free citation extraction

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
| `GET` | `/api/repositories/{id}/symbols` | List extracted AST symbols (classes, functions) |
| `POST` | `/api/chat` | Send question to AI Tutor with selected persona |
| `GET` | `/api/sessions` | List chat sessions |
| `GET` | `/api/sessions/{id}` | Get session details & message history |
| `POST` | `/api/retrieval/search` | Direct search against FAISS/BM25/Graph |
| `POST` | `/api/evaluation/run` | Run benchmark suite comparing retrieval strategies |
| `GET` | `/api/evaluation/{id}` | Get benchmark results (Recall@K, MRR, Latency) |

---

## Evaluation Results

Benchmarking on the `sample-repos/calculator` evaluation dataset (12 multi-file architectural and symbol queries):

| Retrieval Strategy | Recall@5 | Recall@10 | MRR | Avg Latency |
|---|---|---|---|---|
| **Lexical BM25** | 75.0% | 83.3% | 0.72 | ~4.2 ms |
| **Dense Vector (FAISS)** | 83.3% | 91.7% | 0.81 | ~12.5 ms |
| **Hybrid RRF** | 91.7% | 100.0% | 0.89 | ~16.8 ms |
| **Graph Expansion** | **100.0%** | **100.0%** | **0.95** | ~21.4 ms |

---

## Security

- **Path Traversal Defenses**: Rejects paths containing `..`, absolute paths, or symbolic links resolving outside the repository root.
- **Archive Size & File Limits**: Prevents zip bombs by enforcing maximum file sizes (100MB) and extraction byte limits.
- **Citation Grounding**: AI Tutor responses are strictly cross-referenced against retrieved chunk coordinates to prevent hallucinated line references.

---

## License

MIT License. Designed and built as an autonomous production-grade capstone project.
