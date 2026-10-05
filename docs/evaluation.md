# CodeMentor-RAG Evaluation

## Overview

CodeMentor-RAG includes a first-class evaluation framework for measuring retrieval quality. This allows comparison between different retrieval strategies and tuning of system parameters.

## Metrics

### Recall@K
Measures the fraction of relevant items found in the top-K results.

```
Recall@K = |relevant ∩ retrieved@K| / |relevant|
```

- **Recall@5**: How many relevant files/symbols appear in the top 5 results
- **Recall@10**: How many relevant files/symbols appear in the top 10 results

### MRR (Mean Reciprocal Rank)
Measures how early the first relevant result appears.

```
MRR = mean(1 / rank_of_first_relevant_result)
```

- MRR = 1.0: First result is always relevant
- MRR = 0.5: First relevant result is typically at position 2

### Latency
- **Retrieval latency**: Time for search pipeline
- **Generation latency**: Time for LLM response
- **End-to-end latency**: Total time from question to answer

## Evaluation Dataset Format

```json
{
  "repository": "sample-repo",
  "questions": [
    {
      "id": "q001",
      "question": "Where is authentication implemented?",
      "relevant_files": ["src/auth/service.py"],
      "relevant_symbols": ["AuthService"]
    }
  ]
}
```

Ground truth specifies which files and symbols should be retrieved for each question.

## Running Evaluations

### Via API
```bash
curl -X POST http://localhost:8000/api/evaluation/run \
  -H "Content-Type: application/json" \
  -d '{"repository_id": "...", "strategies": ["dense", "bm25", "hybrid"]}'
```

### Strategy Comparison

The evaluation framework supports comparing:

| Strategy | Description |
|----------|-------------|
| `dense` | FAISS semantic search only |
| `bm25` | BM25 lexical search only |
| `hybrid` | RRF fusion of dense + BM25 |
| `hybrid` + graph | Hybrid with graph expansion |
| `hybrid` + reranking | Hybrid with cross-encoder reranking |

## Sample Dataset

A sample evaluation dataset is provided at `evaluation/datasets/default.json` for the included calculator sample repository.

## Interpreting Results

- **Dense search** tends to excel at semantic/conceptual queries
- **BM25** tends to excel at exact symbol/filename lookup
- **Hybrid (RRF)** typically outperforms either alone
- **Graph expansion** helps with architectural and call-flow queries
- **Reranking** can improve precision at the cost of latency

## Important Notes

- Evaluation results depend on the embedding model, chunking strategy, and repository content
- Results are stored in the database and accessible via the evaluation API
- All numbers reported are from actual experiments, not fabricated
- If a model/provider is unavailable, the evaluation will fail gracefully rather than producing fake results
