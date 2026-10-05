# CodeMentor-RAG Retrieval Pipeline

## Overview

CodeMentor-RAG implements a multi-stage retrieval pipeline designed specifically for code repositories. The pipeline combines dense semantic search with lexical search, fuses results using Reciprocal Rank Fusion (RRF), expands context using a code graph, and optionally applies diversification and reranking.

## Pipeline Stages

### 1. Query Analysis

Before retrieval, the query is analyzed to determine intent and routing:

| Intent | Example | Strategy |
|--------|---------|----------|
| REPOSITORY_OVERVIEW | "What does this repo do?" | Emphasize semantic search |
| SYMBOL_LOOKUP | "Where is UserService defined?" | Emphasize lexical/BM25 |
| ARCHITECTURE | "Explain the architecture" | Hybrid + graph |
| CALL_FLOW | "What calls validateToken?" | Symbol search + graph |
| DEBUGGING | "Help me debug this error" | Hybrid + graph |
| IMPLEMENTATION_EXPLANATION | "How does auth work?" | Hybrid + multi-file |

### 2. Code-Aware Chunking

Unlike generic text chunking, CodeMentor-RAG creates chunks aligned to code structure:

```
File
 ├── File Overview (imports + symbol signatures)
 ├── Class: UserService
 │    ├── Method: authenticate()
 │    └── Method: validate_token()
 ├── Function: create_app()
 └── Module-level code
```

Each chunk retains metadata:
- `file_path`, `language`, `symbol_name`, `symbol_type`
- `parent_symbol`, `start_line`, `end_line`
- `imports`, `definitions`, `content_hash`

### 3. Dense Retrieval (FAISS)

- Uses sentence-transformers (`all-MiniLM-L6-v2` by default)
- Embeddings are normalized and stored in a FAISS `IndexFlatIP` (inner product)
- Retrieves top-K semantically similar chunks

### 4. BM25 Lexical Retrieval

- Custom BM25 implementation with code-aware tokenization
- Tokenizer splits identifiers:
  - `getUserProfile` → `["getuserprofile", "get", "user", "profile"]`
  - `get_user_profile` → `["get_user_profile", "get", "user", "profile"]`
- Critical for exact symbol/filename lookup

### 5. Reciprocal Rank Fusion (RRF)

Combines dense and BM25 results without comparing incomparable scores:

```
RRF(d) = Σ weight_i / (k + rank_i(d))
```

- `k` = 60 (configurable via `RRF_K`)
- Dense weight adjusted based on query intent:
  - Symbol lookup → more BM25 weight (0.4 dense)
  - Semantic questions → more dense weight (0.6 dense)

### 6. Graph Expansion (Small-to-Big Retrieval)

When a method is retrieved, the system can expand to include:
- Parent class definition
- Relevant imports
- Callers/callees (via code graph)
- Containing file overview

Graph relationships used:
- `CONTAINS` (file→class, class→method)
- `CALLS` (function→function)
- `INHERITS` (child→parent class)
- `IMPORTS` (file→symbol)

### 7. MMR Diversification

Maximal Marginal Relevance reduces redundant chunks:

```
MMR = λ × relevance(q, d) − (1−λ) × max_sim(d, selected)
```

- `λ` = 0.7 (configurable via `MMR_LAMBDA`)
- Uses file/line overlap as similarity metric
- Ensures diverse files are represented

### 8. Optional Reranking

Cross-encoder reranking (when enabled):
- Uses `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Scores (query, chunk) pairs with a cross-attention model
- More accurate but slower than bi-encoder search

## Context Budgeting

The final context sent to the LLM is token-budgeted:
1. Chunks are ordered by retrieval score
2. Each chunk is added until the budget is reached
3. Overlapping line ranges are deduplicated
4. Chunks include source annotations for citation generation

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DENSE_TOP_K` | 20 | Dense retrieval candidates |
| `BM25_TOP_K` | 20 | BM25 retrieval candidates |
| `FINAL_TOP_K` | 10 | Final results after fusion |
| `RRF_K` | 60 | RRF constant |
| `MMR_ENABLED` | true | Enable MMR diversification |
| `MMR_LAMBDA` | 0.7 | MMR relevance/diversity balance |
| `RERANK_ENABLED` | false | Enable cross-encoder reranking |
| `CONTEXT_TOKEN_BUDGET` | 4096 | Max tokens for LLM context |
