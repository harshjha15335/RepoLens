#!/usr/bin/env python3
"""Run offline retrieval benchmarks against CodeMentor-RAG API."""

import json
import time
import httpx
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000/api"
DATASET_PATH = Path(__file__).resolve().parent.parent / "evaluation" / "datasets" / "default.json"


def main():
    print("=" * 60)
    print("CodeMentor-RAG Retrieval Strategy Benchmark Runner")
    print("=" * 60)

    # 1. Check dataset
    if not DATASET_PATH.exists():
        print(f"Error: Dataset not found at {DATASET_PATH}")
        return

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    questions = dataset.get("questions", [])
    print(f"Loaded {len(questions)} evaluation questions from {DATASET_PATH.name}")

    # 2. Get repository
    repos = httpx.get(f"{BASE_URL}/repositories").json().get("repositories", [])
    repo = next((r for r in repos if r["status"] == "ready"), None)

    if not repo:
        print("Error: No indexed repository in READY state found.")
        print("Run `python scripts/seed_demo.py` first to index the sample repository.")
        return

    repo_id = repo["id"]
    print(f"Benchmarking against repository: '{repo['name']}' ({repo_id})\n")

    strategies = ["bm25", "dense", "hybrid_rrf", "graph_expansion"]
    summary = {}

    for strat in strategies:
        print(f"Evaluating strategy: [{strat.upper()}]...")
        hits_at_5 = 0
        hits_at_10 = 0
        rr_sum = 0.0
        latencies = []

        for q in questions:
            t0 = time.perf_counter()
            resp = httpx.post(
                f"{BASE_URL}/retrieval/search",
                json={
                    "repository_id": repo_id,
                    "query": q["question"],
                    "strategy": strat,
                    "top_k": 10,
                    "enable_graph_expansion": (strat == "graph_expansion"),
                    "enable_mmr": True,
                },
                timeout=20.0,
            )
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                chunks = data.get("chunks", [])
                retrieved_files = [c["file_path"] for c in chunks]
                target_files = set(q.get("relevant_files", []))

                # Check hits
                top5_files = set(retrieved_files[:5])
                top10_files = set(retrieved_files[:10])

                if top5_files.intersection(target_files):
                    hits_at_5 += 1
                if top10_files.intersection(target_files):
                    hits_at_10 += 1

                # Reciprocal rank
                rr = 0.0
                for rank, f_path in enumerate(retrieved_files, 1):
                    if f_path in target_files:
                        rr = 1.0 / rank
                        break
                rr_sum += rr

        total = len(questions)
        summary[strat] = {
            "recall_5": hits_at_5 / total if total else 0,
            "recall_10": hits_at_10 / total if total else 0,
            "mrr": rr_sum / total if total else 0,
            "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
        }

    # Print Results Table
    print("\n" + "=" * 65)
    print(f"{'Strategy':<18} | {'Recall@5':<10} | {'Recall@10':<10} | {'MRR':<8} | {'Latency':<8}")
    print("-" * 65)
    for strat, m in summary.items():
        print(
            f"{strat:<18} | {m['recall_5']*100:>7.1f}%  | {m['recall_10']*100:>7.1f}%  | {m['mrr']:>7.3f} | {m['avg_latency']:>6.1f}ms"
        )
    print("=" * 65)


if __name__ == "__main__":
    main()
