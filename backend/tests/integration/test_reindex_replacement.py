"""Repeated indexing replaces repository records instead of duplicating them."""

import zipfile

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import repositories
from app.core.config import Settings
from app.core.database import Base
from app.models.models import (
    Chunk,
    GraphEdge,
    GraphNode,
    Repository,
    RepositoryFile,
    RepositoryStatus,
)
from app.services.ingestion import service as ingestion


async def test_reindex_twice_replaces_files_chunks_and_graph(tmp_path, monkeypatch):
    settings = Settings(data_dir=str(tmp_path / "data"))
    monkeypatch.setattr(ingestion, "get_settings", lambda: settings)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(ingestion, "get_session_factory", lambda: factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    class FakeEmbeddings:
        metadata = {"provider": "test", "model": "test", "dimension": 1, "version": 1, "fingerprint": "test"}

        async def embed_documents(self, texts):
            return [[1.0] for _ in texts]

    index_sizes = []

    class FakeIndex:
        async def build_indexes(self, repository_id, chunks, embeddings, embedding_metadata):
            index_sizes.append(len(chunks))
            assert len(chunks) == len(embeddings)
            assert embedding_metadata == FakeEmbeddings.metadata

    monkeypatch.setattr(ingestion, "EmbeddingService", FakeEmbeddings)
    monkeypatch.setattr(ingestion, "IndexingService", FakeIndex)

    storage = tmp_path / "calculator"
    storage.mkdir()
    archive = storage / "source.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("README.md", "A calculator with arithmetic and history.\n")
        zf.writestr("src/calculator.py", "class Calculator:\n    def add(self, a, b):\n        return a + b\n")

    try:
        async with factory() as db:
            repo = Repository(name="calculator", source_type="zip", storage_path=str(storage))
            db.add(repo)
            await db.commit()
            repository_id = repo.id

        snapshots = []
        for _ in range(2):
            await ingestion.IngestionService.run_ingestion(repository_id, str(archive), "zip")
            async with factory() as db:
                repo = await db.get(Repository, repository_id)
                assert repo.status == RepositoryStatus.READY, repo.error_message
                counts = []
                for model in (RepositoryFile, Chunk, GraphNode, GraphEdge):
                    counts.append((await db.scalar(
                        select(func.count()).select_from(model).where(model.repository_id == repository_id)
                    )))
                files = (await db.execute(
                    select(RepositoryFile.path).where(RepositoryFile.repository_id == repository_id)
                )).scalars().all()
                assert sorted(path.replace("\\", "/") for path in files) == [
                    "README.md", "src/calculator.py",
                ]
                assert counts[0] == repo.file_count == 2
                assert counts[1] == repo.chunk_count
                assert counts[2] == repo.graph_node_count
                assert counts[3] == repo.graph_edge_count
                response = await repositories.get_file_content(repository_id, path="README.md", db=db)
                assert "calculator" in response.content
                snapshots.append(counts)

        assert snapshots[0] == snapshots[1]
        assert index_sizes == [snapshots[0][1], snapshots[1][1]]
    finally:
        await engine.dispose()
