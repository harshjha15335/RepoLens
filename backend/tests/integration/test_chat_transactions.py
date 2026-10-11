"""Slow chat generation must not block independent SQLite writes."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import chat as chat_api
from app.core.database import Base
from app.models.models import ChatMessage, ChatSession, Repository, RepositoryStatus
from app.schemas.schemas import ChatRequest


@pytest.mark.parametrize("existing_session", [False, True])
@pytest.mark.parametrize("generation_fails", [False, True])
async def test_generation_releases_database_and_persists_only_success(
    tmp_path, monkeypatch, existing_session, generation_fails
):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}", connect_args={"timeout": 0.1}
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as setup:
        repo = Repository(name="chat", source_type="zip", status=RepositoryStatus.READY)
        setup.add(repo)
        await setup.flush()
        session = ChatSession(repository_id=repo.id, tutor_mode="developer")
        if existing_session:
            setup.add(session)
        await setup.commit()
        repo_id = repo.id
        session_id = session.id if existing_session else None

    class Generation:
        async def generate_answer(self, **kwargs):
            # This write uses a separate connection while chat is generating.
            async with factory() as writer:
                writer.add(Repository(name="concurrent upload", source_type="zip"))
                await writer.commit()
            if generation_fails:
                raise RuntimeError("model unavailable")
            return {"answer": "Answer", "citations": [], "metadata": {}}

    monkeypatch.setattr(chat_api, "GenerationService", Generation)
    try:
        async with factory() as request_db:
            request = ChatRequest(repository_id=repo_id, session_id=session_id, question="Explain")
            if generation_fails:
                with pytest.raises(RuntimeError, match="model unavailable"):
                    await chat_api.chat(request, request_db)
                await request_db.rollback()
            else:
                response = await chat_api.chat(request, request_db)
                assert response.answer == "Answer"
                await request_db.commit()
        async with factory() as verification:
            count = await verification.scalar(select(func.count()).select_from(ChatMessage))
            assert count == (0 if generation_fails else 2)
            assert await verification.scalar(select(func.count()).select_from(Repository)) == 2
    finally:
        await engine.dispose()
