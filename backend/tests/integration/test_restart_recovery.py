"""Stopped jobs become visibly retryable; completed data survives restart."""

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main
from app.core.database import Base
from app.models.models import EvaluationRun, Repository, RepositoryStatus
from app.schemas.schemas import ChatRequest


async def test_restart_recovers_only_unfinished_jobs(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(main, "get_session_factory", lambda: factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with factory() as db:
            interrupted = Repository(name="unfinished", source_type="zip", status=RepositoryStatus.INDEXING)
            ready = Repository(name="ready", source_type="zip", status=RepositoryStatus.READY)
            db.add_all([interrupted, ready])
            await db.flush()
            running = EvaluationRun(repository_id=ready.id, strategy="bm25", status="running")
            completed = EvaluationRun(repository_id=ready.id, strategy="bm25", status="completed")
            db.add_all([running, completed])
            await db.commit()
        await main.recover_interrupted_jobs()
        async with factory() as db:
            assert (await db.get(Repository, interrupted.id)).status == RepositoryStatus.FAILED
            assert (await db.get(Repository, ready.id)).status == RepositoryStatus.READY
            recovered = await db.get(EvaluationRun, running.id)
            assert recovered.status == "failed"
            assert recovered.completed_at is not None
            assert "restart" in recovered.results[0]["error"]
            assert (await db.get(EvaluationRun, completed.id)).status == "completed"
    finally:
        await engine.dispose()


def test_unsupported_streaming_is_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(repository_id="repo", question="Explain this", stream=True)
