"""A fresh service instance can reconstruct source and search files from SQL."""

import io
import shutil
import zipfile

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.database import Base
from app.core.errors import RepositoryValidationError
from app.models.models import Repository
from app.services import artifact_store


async def test_source_and_search_indexes_survive_ephemeral_disk_loss(tmp_path, monkeypatch):
    settings = Settings(data_dir=str(tmp_path / "ephemeral"))
    monkeypatch.setattr(artifact_store, "get_settings", lambda: settings)
    monkeypatch.setattr(artifact_store, "enabled", lambda db: True)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'durable.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with factory() as db:
            repo = Repository(name="calculator", source_type="zip", storage_path="/old/instance/path")
            db.add(repo)
            await db.flush()
            source = settings.repos_path / repo.id / "source"
            (source / "src").mkdir(parents=True)
            code = source / "src" / "calc.py"
            code.write_text("def add(a, b): return a + b\n", encoding="utf-8")
            index = settings.indexes_path / repo.id
            index.mkdir(parents=True)
            (index / "bm25.index").write_text('{"version":1}', encoding="utf-8")
            (index / "metadata.json").write_text('{"embedding":{}}', encoding="utf-8")
            archive = settings.repos_path / repo.id / "source.zip"
            archive.write_bytes(b"original upload")
            await artifact_store.save_file(db, repo.id, artifact_store.SOURCE_ZIP, archive)
            await artifact_store.save_source_tree(db, repo.id, source, [code])
            await artifact_store.save_index(db, repo.id)
            await db.commit()
            repo_id = repo.id

        shutil.rmtree(settings.repos_path / repo_id)
        shutil.rmtree(settings.indexes_path / repo_id)

        async with factory() as db:
            repo = await db.get(Repository, repo_id)
            await artifact_store.ensure_upload(db, repo)
            await artifact_store.ensure_source(db, repo)
            await artifact_store.ensure_index(db, repo_id)
            assert repo.storage_path == str(settings.repos_path / repo_id)
            assert (settings.repos_path / repo_id / "source.zip").read_bytes() == b"original upload"
            assert (settings.repos_path / repo_id / "source/src/calc.py").read_text() == "def add(a, b): return a + b\n"
            assert (settings.indexes_path / repo_id / "bm25.index").read_text() == '{"version":1}'
            assert (settings.indexes_path / repo_id / "metadata.json").is_file()

        # A reindex on another instance replaces the durable snapshot. This
        # instance must refresh its already-restored local copy on next use.
        async with factory() as db:
            replacement = tmp_path / "new-index"
            replacement.mkdir()
            (replacement / "bm25.index").write_text('{"version":2}', encoding="utf-8")
            await artifact_store.save_bytes(
                db, repo_id, artifact_store.SEARCH_INDEX,
                artifact_store._archive_files(replacement, [replacement / "bm25.index"]),
            )
            await db.commit()
        async with factory() as db:
            await artifact_store.ensure_index(db, repo_id)
            assert (settings.indexes_path / repo_id / "bm25.index").read_text() == '{"version":2}'
            assert not (settings.indexes_path / repo_id / "metadata.json").exists()
    finally:
        await engine.dispose()


async def test_rejects_path_traversal_in_stored_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact_store, "get_settings", lambda: Settings(data_dir=str(tmp_path)))
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("../outside.py", "bad")
    with pytest.raises(RepositoryValidationError):
        artifact_store._restore_archive(payload.getvalue(), tmp_path / "source", 1024)
    assert not (tmp_path / "outside.py").exists()
