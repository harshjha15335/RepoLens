"""Dense retrieval must stay in the vector space used during indexing."""

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from app.core.config import Settings
from app.core.errors import IndexError_
from app.services.embeddings import service as embeddings
from app.services.indexing import service as indexing
from app.services.retrieval.service import RetrievalService


async def test_sentence_transformer_load_is_cache_only(monkeypatch):
    constructor = Mock(side_effect=OSError("model is not cached"))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(
        SentenceTransformer=constructor,
    ))
    provider = embeddings.SentenceTransformerProvider("missing-model")
    vectors = await provider.embed_documents(["def square(x): return x * x"])
    local = embeddings.DeterministicLocalEmbeddingProvider()

    constructor.assert_called_once_with("missing-model", local_files_only=True)
    assert provider.metadata == local.metadata
    assert vectors == await local.embed_documents(["def square(x): return x * x"])


async def test_batch_failure_reembeds_every_document_with_one_provider():
    model = Mock()
    model.encode.side_effect = [np.ones((64, 384)), RuntimeError("second batch fails")]
    provider = embeddings.SentenceTransformerProvider("cached-model")
    provider._model = model
    provider._dimension = 384
    texts = [f"def method_{i}(): return {i}" for i in range(65)]

    result = await provider.embed_documents(texts)
    local = embeddings.DeterministicLocalEmbeddingProvider()
    assert result == await local.embed_documents(texts)
    assert provider.metadata == local.metadata


@pytest.mark.parametrize("change", ["provider", "model", "fingerprint"])
async def test_same_dimension_identity_change_blocks_faiss_search(change):
    local = embeddings.DeterministicLocalEmbeddingProvider()
    indexed_metadata = local.metadata
    query_metadata = {**indexed_metadata, change: "changed"}
    search = Mock()
    retrieval = RetrievalService.__new__(RetrievalService)
    retrieval.indexing_service = SimpleNamespace(
        load_faiss_index=lambda _: SimpleNamespace(d=384, ntotal=1, search=search),
        load_embedding_metadata=lambda _: indexed_metadata,
    )
    retrieval.embedding_service = SimpleNamespace(
        embed_query=AsyncMock(return_value=[1.0] * 384), metadata=query_metadata,
    )

    with pytest.raises(IndexError_, match="Reindex"):
        await retrieval._dense_search("repo", "square", 5)
    search.assert_not_called()


async def test_query_fallback_identity_is_checked_after_embedding():
    local = embeddings.DeterministicLocalEmbeddingProvider()
    provider = embeddings.SentenceTransformerProvider("cached-model")
    provider._dimension = 384
    provider._model = Mock()
    provider._model.encode.side_effect = RuntimeError("cached model encoding failed")
    indexed_metadata = provider.metadata
    search = Mock()
    retrieval = RetrievalService.__new__(RetrievalService)
    retrieval.indexing_service = SimpleNamespace(
        load_faiss_index=lambda _: SimpleNamespace(d=384, ntotal=1, search=search),
        load_embedding_metadata=lambda _: indexed_metadata,
    )
    # A real service exposes live provider metadata, not a pre-encoding snapshot.
    service = embeddings.EmbeddingService.__new__(embeddings.EmbeddingService)
    service.provider = provider
    retrieval.embedding_service = service

    with pytest.raises(IndexError_, match="Reindex"):
        await retrieval._dense_search("repo", "square", 5)
    assert provider.metadata == local.metadata
    search.assert_not_called()


@pytest.mark.parametrize("metadata", [None, {"embedding_model": "all-MiniLM-L6-v2"}, {"embedding": {}}])
async def test_missing_identity_fails_before_embedding_bm25_remains_usable(tmp_path, monkeypatch, metadata):
    settings = Settings(data_dir=str(tmp_path))
    monkeypatch.setattr(indexing, "get_settings", lambda: settings)
    index_dir = settings.indexes_path / "repo"
    index_dir.mkdir(parents=True)
    if metadata is not None:
        (index_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    bm25 = indexing.BM25Index()
    bm25.build([{"content": "def square(x): return x * x", "content_hash": "square"}])
    bm25.save(str(index_dir / "bm25.index"))
    retrieval = RetrievalService.__new__(RetrievalService)
    retrieval.indexing_service = indexing.IndexingService()
    monkeypatch.setattr(retrieval.indexing_service, "load_faiss_index", lambda _: Mock())
    retrieval.embedding_service = SimpleNamespace(embed_query=AsyncMock())

    with pytest.raises(IndexError_, match="metadata.*Reindex"):
        await retrieval._dense_search("repo", "square", 5)
    retrieval.embedding_service.embed_query.assert_not_awaited()
    assert retrieval._bm25_search("repo", "square", 5)[0][0] == 0
