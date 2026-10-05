"""Retrieval evaluation service with Recall@K, MRR, and latency metrics."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import EvaluationError
from app.core.logging import get_logger
from app.models.models import EvaluationRun
from app.services.retrieval.service import RetrievalService

logger = get_logger(__name__)


class EvaluationService:
    """Runs retrieval evaluation experiments."""

    @staticmethod
    async def run_evaluation(
        evaluation_id: str,
        repository_id: str,
        strategies: list[str],
        dataset_path: str | None = None,
    ):
        """Run retrieval evaluation as a background task."""
        factory = get_session_factory()
        settings = get_settings()

        async with factory() as db:
            try:
                eval_run = await db.get(EvaluationRun, evaluation_id)
                if not eval_run:
                    logger.error(f"Evaluation {evaluation_id} not found")
                    return

                # Load evaluation dataset
                dataset = EvaluationService._load_dataset(dataset_path, settings)
                if not dataset or not dataset.get("questions"):
                    raise EvaluationError("No evaluation questions found")

                questions = dataset["questions"]
                retrieval = RetrievalService()

                all_results = []

                for strategy in strategies:
                    strategy_results = {
                        "strategy": strategy,
                        "recall_at_5": 0.0,
                        "recall_at_10": 0.0,
                        "mrr": 0.0,
                        "avg_latency_ms": 0.0,
                        "question_results": [],
                    }

                    total_recall_5 = 0.0
                    total_recall_10 = 0.0
                    total_mrr = 0.0
                    total_latency = 0.0
                    n_questions = 0

                    for q in questions:
                        question_text = q.get("question", "")
                        relevant_files = set(q.get("relevant_files", []))
                        relevant_symbols = set(q.get("relevant_symbols", []))

                        if not question_text:
                            continue

                        # Run retrieval
                        start = time.time()
                        try:
                            result = await retrieval.search(
                                repository_id=repository_id,
                                query=question_text,
                                top_k=10,
                                strategy=strategy,
                                enable_graph_expansion=(strategy == "hybrid"),
                                enable_mmr=False,  # Disable MMR for fair eval
                                enable_reranking=False,
                            )
                        except Exception as e:
                            logger.warning(f"Retrieval failed for '{question_text}': {e}")
                            continue

                        latency = (time.time() - start) * 1000
                        chunks = result.get("chunks", [])

                        # Calculate metrics
                        recall_5 = EvaluationService._calculate_recall(
                            chunks[:5], relevant_files, relevant_symbols
                        )
                        recall_10 = EvaluationService._calculate_recall(
                            chunks[:10], relevant_files, relevant_symbols
                        )
                        rr = EvaluationService._calculate_reciprocal_rank(
                            chunks, relevant_files, relevant_symbols
                        )

                        total_recall_5 += recall_5
                        total_recall_10 += recall_10
                        total_mrr += rr
                        total_latency += latency
                        n_questions += 1

                        strategy_results["question_results"].append({
                            "question_id": q.get("id", ""),
                            "question": question_text,
                            "recall_at_5": round(recall_5, 4),
                            "recall_at_10": round(recall_10, 4),
                            "reciprocal_rank": round(rr, 4),
                            "latency_ms": round(latency, 2),
                            "retrieved_files": [
                                c.get("file_path", "") for c in chunks[:5]
                            ],
                        })

                    if n_questions > 0:
                        strategy_results["recall_at_5"] = round(
                            total_recall_5 / n_questions, 4
                        )
                        strategy_results["recall_at_10"] = round(
                            total_recall_10 / n_questions, 4
                        )
                        strategy_results["mrr"] = round(
                            total_mrr / n_questions, 4
                        )
                        strategy_results["avg_latency_ms"] = round(
                            total_latency / n_questions, 2
                        )

                    all_results.append(strategy_results)

                    logger.info(
                        f"Evaluation [{strategy}]: "
                        f"R@5={strategy_results['recall_at_5']}, "
                        f"R@10={strategy_results['recall_at_10']}, "
                        f"MRR={strategy_results['mrr']}, "
                        f"avg_lat={strategy_results['avg_latency_ms']}ms"
                    )

                # Update evaluation record
                eval_run.status = "completed"
                eval_run.completed_at = datetime.now(timezone.utc)
                eval_run.results = all_results

                if all_results:
                    primary = all_results[0]
                    eval_run.recall_at_5 = primary["recall_at_5"]
                    eval_run.recall_at_10 = primary["recall_at_10"]
                    eval_run.mrr = primary["mrr"]
                    eval_run.avg_retrieval_latency_ms = primary["avg_latency_ms"]

                await db.commit()
                logger.info(f"Evaluation {evaluation_id} completed")

            except Exception as e:
                logger.exception(f"Evaluation failed: {e}")
                try:
                    eval_run = await db.get(EvaluationRun, evaluation_id)
                    if eval_run:
                        eval_run.status = "failed"
                        eval_run.results = [{"error": str(e)}]
                        await db.commit()
                except Exception:
                    pass

    @staticmethod
    def _load_dataset(dataset_path: str | None, settings) -> dict | None:
        """Load evaluation dataset from file."""
        if dataset_path:
            path = Path(dataset_path)
        else:
            # Default dataset location
            path = Path("evaluation/datasets/default.json")

        if not path.exists():
            # Try relative to project root
            alt_paths = [
                Path("evaluation/datasets/default.json"),
                Path("evaluation/datasets/sample.json"),
            ]
            for alt in alt_paths:
                if alt.exists():
                    path = alt
                    break
            else:
                logger.warning("No evaluation dataset found")
                return None

        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            return None

    @staticmethod
    def _calculate_recall(
        chunks: list[dict],
        relevant_files: set[str],
        relevant_symbols: set[str],
    ) -> float:
        """Calculate recall - fraction of relevant items found."""
        if not relevant_files and not relevant_symbols:
            return 0.0

        total_relevant = len(relevant_files) + len(relevant_symbols)
        found = 0

        retrieved_files = set()
        retrieved_symbols = set()

        for chunk in chunks:
            file_path = chunk.get("file_path", "")
            symbol = chunk.get("symbol_name", "")

            retrieved_files.add(file_path)
            if symbol:
                retrieved_symbols.add(symbol)

        # Check file matches (partial path matching)
        for rel_file in relevant_files:
            for ret_file in retrieved_files:
                if ret_file.endswith(rel_file) or rel_file in ret_file:
                    found += 1
                    break

        # Check symbol matches
        for rel_sym in relevant_symbols:
            if rel_sym in retrieved_symbols:
                found += 1

        return found / total_relevant if total_relevant > 0 else 0.0

    @staticmethod
    def _calculate_reciprocal_rank(
        chunks: list[dict],
        relevant_files: set[str],
        relevant_symbols: set[str],
    ) -> float:
        """Calculate reciprocal rank - 1/position of first relevant result."""
        for i, chunk in enumerate(chunks):
            file_path = chunk.get("file_path", "")
            symbol = chunk.get("symbol_name", "")

            # Check file match
            for rel_file in relevant_files:
                if file_path.endswith(rel_file) or rel_file in file_path:
                    return 1.0 / (i + 1)

            # Check symbol match
            if symbol in relevant_symbols:
                return 1.0 / (i + 1)

        return 0.0
