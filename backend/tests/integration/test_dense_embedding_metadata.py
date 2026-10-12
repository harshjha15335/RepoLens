"""A saved dense index carries the actual embedding identity through retrieval."""

import json

import pytest

from app.core.config import Settings
from app.services.embeddings.service import DeterministicLocalEmbeddingProvider, EmbeddingService
from app.services.indexing import service as indexing
from app.services.retrieval.service import RetrievalService


@pytest.mark.skipif(not indexing.FAISS_AVAILABLE, reason="FAISS is unavailable")
async def test_matching_local_provider_build_and_dense_search(tmp_path, monkeypatch):
    settings = Settings(data_dir=str(tmp_path), embedding_model="configured-transformer")
    monkeypatch.setattr(indexing, "get_settings", lambda: settings)
    provider = DeterministicLocalEmbeddingProvider()
    chunks = [
        {"content": "def square(x): return x * x", "content_hash": "square"},
        {"content": "def greet(name): return 'hello ' + name", "content_hash": "greet"},
    ]
    service = indexing.IndexingService()
    await service.build_indexes(
        "repo", chunks, await provider.embed_documents([c["content"] for c in chunks]),
        embedding_metadata=provider.metadata,
    )
    metadata = json.loads((settings.indexes_path / "repo" / "metadata.json").read_text())
    assert metadata["embedding"] == provider.metadata
    assert metadata["embedding_model"] == provider.model_name
    assert metadata["embedding_model"] != settings.embedding_model

    embedding_service = EmbeddingService.__new__(EmbeddingService)
    embedding_service.provider = provider
    retrieval = RetrievalService.__new__(RetrievalService)
    retrieval.indexing_service = service
    retrieval.embedding_service = embedding_service
    results = await retrieval._dense_search("repo", chunks[0]["content"], 5)
    assert results[0][0] == 0
    assert results[0][1] == pytest.approx(1.0)
