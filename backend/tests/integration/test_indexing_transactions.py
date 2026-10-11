"""Workers must see committed repository state before request teardown."""

import io
import zipfile
import pytest
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import repositories
from app.core.config import Settings
from app.core.database import Base
from app.models.models import Repository, RepositoryStatus
from app.schemas.schemas import GitImportRequest


@pytest.mark.parametrize("operation", ["upload", "git", "reindex"])
async def test_indexer_sees_committed_repository_before_request_finishes(tmp_path, monkeypatch, operation):
    settings = Settings(data_dir=str(tmp_path / "data"))
    monkeypatch.setattr(repositories, "get_settings", lambda: settings)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("main.py", "def add(a, b): return a + b\n")
    archive.seek(0)
    jobs = []

    async def indexer(repository_id, source, source_type, branch=None):
        # A distinct connection models the background worker, before get_db's
        # yield dependency has committed or closed the request session.
        async with factory() as worker:
            repo = await worker.get(Repository, repository_id)
            assert repo is not None, "Background worker cannot see the upload"
            assert repo.status == RepositoryStatus.PENDING
            assert repo.progress == 0
            assert repo.error_message is None
            assert repo.storage_path
            if source_type == "zip":
                assert zipfile.is_zipfile(source), "Reindex must receive the archive, not its directory"
            else:
                assert source == "https://github.com/example/calculator.git"
                assert branch == "main"
            repo.status = RepositoryStatus.DISCOVERING
            repo.progress = 5
            await worker.commit()
            jobs.append(repository_id)

    monkeypatch.setattr(repositories.IngestionService, "run_ingestion", indexer)
    try:
        async with factory() as request:
            tasks = BackgroundTasks()
            if operation == "upload":
                result = await repositories.upload_repository(
                    file=UploadFile(filename="calculator.zip", file=archive),
                    background_tasks=tasks, db=request,
                )
            elif operation == "git":
                result = await repositories.import_git_repository(
                    request=GitImportRequest(url="https://github.com/example/calculator.git", branch="main"),
                    background_tasks=tasks, db=request,
                )
            else:
                storage = settings.repos_path / "existing"
                storage.mkdir()
                (storage / "source.zip").write_bytes(archive.getvalue())
                repo = Repository(name="calculator", source_type="zip", storage_path=str(storage),
                                  status=RepositoryStatus.FAILED, progress=65, error_message="old failure")
                request.add(repo)
                await request.commit()
                result = await repositories.reindex_repository(repo.id, background_tasks=tasks, db=request)
            await tasks()
            await request.commit()
        assert jobs == [result.id]
        async with factory() as verification:
            repo = await verification.get(Repository, result.id)
            assert repo.status == RepositoryStatus.DISCOVERING
            assert repo.progress == 5
    finally:
        await engine.dispose()
