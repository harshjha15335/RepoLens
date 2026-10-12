"""Evaluation jobs must be visible to workers and return per-strategy results."""

import json

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import evaluation
from app.core.database import Base
from app.models.models import Repository, RepositoryStatus
from app.schemas.schemas import EvaluationRequest
from app.services.evaluation import service


async def test_background_evaluation_returns_four_distinct_strategies(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(service, "get_session_factory", lambda: factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    dataset = tmp_path / "questions.json"
    monkeypatch.setattr(service, "DEFAULT_DATASET", tmp_path / "default.json")
    dataset.write_text(json.dumps({"questions": [{
        "id": "q1", "question": "Find Calculator", "relevant_files": ["src/calculator.py"],
    }]}), encoding="utf-8")
    calls = []

    class FakeRetrieval:
        async def search(self, **kwargs):
            calls.append((kwargs["strategy"], kwargs["enable_graph_expansion"]))
            return {"chunks": [{"file_path": "src\\calculator.py", "symbol_name": "Calculator"}]}

    monkeypatch.setattr(service, "RetrievalService", FakeRetrieval)
    try:
        async with factory() as request_db:
            repo = Repository(name="calculator", source_type="zip", status=RepositoryStatus.READY)
            request_db.add(repo)
            await request_db.commit()

            tasks = BackgroundTasks()
            queued = await evaluation.run_evaluation(
                request=EvaluationRequest(
                    repository_id=repo.id,
                    dataset_path=str(dataset),
                    strategies=["bm25", "dense", "hybrid_rrf", "graph_expansion"],
                ),
                background_tasks=tasks,
                db=request_db,
            )
            # This executes before the request dependency's teardown commit.
            await tasks()

        async with factory() as db:
            result = await evaluation.get_evaluation(queued.id, db=db)
        assert result.status == "completed"
        assert [metric.strategy for metric in result.metrics] == [
            "bm25", "dense", "hybrid_rrf", "graph_expansion",
        ]
        assert calls == [
            ("bm25", False), ("dense", False), ("hybrid", False), ("hybrid", True),
        ]
        assert all(metric.recall_at_5 == 1 for metric in result.metrics)
        assert all(metric.results[0]["question_id"] == "q1" for metric in result.metrics)
    finally:
        await engine.dispose()


def test_default_dataset_resolves_from_backend_working_directory(monkeypatch):
    monkeypatch.chdir(service.DEFAULT_DATASET.parents[2] / "backend")
    dataset = service.EvaluationService._load_dataset(None, None)
    assert dataset["repository"] == "calculator"
    assert dataset["questions"]
