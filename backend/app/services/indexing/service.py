"""Indexing service for FAISS dense index and BM25 lexical index."""

import json
import math
import os
import pickle
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.errors import IndexError_
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available. Install with: pip install faiss-cpu")


class BM25Index:
    """BM25 lexical index with code-aware tokenization."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs: dict[str, int] = {}
        self.doc_lens: list[int] = []
        self.avg_dl: float = 0.0
        self.n_docs: int = 0
        self.tf: list[dict[str, int]] = []
        self.chunk_ids: list[str] = []

    def build(self, chunks: list[dict]):
        """Build BM25 index from chunks."""
        self.n_docs = len(chunks)
        self.doc_freqs = {}
        self.doc_lens = []
        self.tf = []
        self.chunk_ids = []

        for chunk in chunks:
            tokens = self._tokenize(chunk)
            self.chunk_ids.append(chunk.get("content_hash", ""))

            tf = Counter(tokens)
            self.tf.append(dict(tf))
            self.doc_lens.append(len(tokens))

            for term in set(tokens):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.avg_dl = sum(self.doc_lens) / self.n_docs if self.n_docs > 0 else 0

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """Search the BM25 index. Returns (doc_index, score) tuples."""
        query_tokens = self._tokenize_query(query)

        scores = []
        for i in range(self.n_docs):
            score = 0.0
            dl = self.doc_lens[i]
            tf = self.tf[i]

            for term in query_tokens:
                if term not in tf:
                    continue

                term_freq = tf[term]
                df = self.doc_freqs.get(term, 0)

                # IDF
                idf = math.log(
                    (self.n_docs - df + 0.5) / (df + 0.5) + 1
                )

                # TF normalization
                tf_norm = (term_freq * (self.k1 + 1)) / (
                    term_freq + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                )

                score += idf * tf_norm

            if score > 0:
                scores.append((i, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def _tokenize(self, chunk: dict) -> list[str]:
        """Tokenize a chunk for BM25 indexing with code-aware splitting."""
        text_parts = []

        # Include content
        content = chunk.get("content", "")
        text_parts.append(content)

        # Include metadata
        if chunk.get("symbol_name"):
            text_parts.append(chunk["symbol_name"])
        if chunk.get("file_path"):
            text_parts.append(chunk["file_path"])

        full_text = " ".join(text_parts)
        return self._split_tokens(full_text)

    def _tokenize_query(self, query: str) -> list[str]:
        """Tokenize a search query."""
        return self._split_tokens(query)

    def _split_tokens(self, text: str) -> list[str]:
        """Split text into tokens with code-identifier awareness."""
        tokens = []

        # Split on whitespace and punctuation
        words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|[0-9]+', text)

        for word in words:
            tokens.append(word.lower())

            # Split camelCase: getUserProfile -> get, user, profile
            camel_parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)', word)
            for part in camel_parts:
                lower_part = part.lower()
                if lower_part != word.lower() and len(lower_part) > 1:
                    tokens.append(lower_part)

            # Split snake_case: get_user_profile -> get, user, profile
            if "_" in word:
                for part in word.split("_"):
                    if part and len(part) > 1:
                        tokens.append(part.lower())

        return tokens

    def save(self, path: str):
        """Save BM25 index to disk."""
        data = {
            "k1": self.k1,
            "b": self.b,
            "doc_freqs": self.doc_freqs,
            "doc_lens": self.doc_lens,
            "avg_dl": self.avg_dl,
            "n_docs": self.n_docs,
            "tf": self.tf,
            "chunk_ids": self.chunk_ids,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    @classmethod
    def load(cls, path: str) -> "BM25Index":
        """Load BM25 index from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        index = cls(k1=data["k1"], b=data["b"])
        index.doc_freqs = data["doc_freqs"]
        index.doc_lens = data["doc_lens"]
        index.avg_dl = data["avg_dl"]
        index.n_docs = data["n_docs"]
        index.tf = data["tf"]
        index.chunk_ids = data["chunk_ids"]
        return index


class IndexingService:
    """Manages FAISS and BM25 indexes for repositories."""

    async def build_indexes(
        self,
        repository_id: str,
        chunks: list[dict],
        embeddings: list[list[float]],
    ):
        """Build both FAISS and BM25 indexes."""
        settings = get_settings()
        index_dir = settings.indexes_path / repository_id
        index_dir.mkdir(parents=True, exist_ok=True)

        # Build FAISS index
        if FAISS_AVAILABLE and embeddings:
            self._build_faiss_index(embeddings, str(index_dir / "faiss.index"))
            logger.info(
                f"FAISS index built: {len(embeddings)} vectors, "
                f"dim={len(embeddings[0])}"
            )
        elif not FAISS_AVAILABLE:
            logger.warning("FAISS not available, skipping dense index")

        # Build BM25 index
        bm25 = BM25Index()
        bm25.build(chunks)
        bm25.save(str(index_dir / "bm25.index"))
        logger.info(f"BM25 index built: {len(chunks)} documents")

        # Save chunk ID mapping
        chunk_mapping = []
        for i, chunk in enumerate(chunks):
            chunk_mapping.append({
                "index": i,
                "content_hash": chunk.get("content_hash"),
                "file_path": chunk.get("file_path"),
                "symbol_name": chunk.get("symbol_name"),
            })

        with open(str(index_dir / "chunk_mapping.json"), "w") as f:
            json.dump(chunk_mapping, f)

        # Save index metadata
        metadata = {
            "repository_id": repository_id,
            "chunk_count": len(chunks),
            "embedding_dimension": len(embeddings[0]) if embeddings else 0,
            "embedding_model": settings.embedding_model,
        }
        with open(str(index_dir / "metadata.json"), "w") as f:
            json.dump(metadata, f)

    def _build_faiss_index(self, embeddings: list[list[float]], path: str):
        """Build and save a FAISS index."""
        if not FAISS_AVAILABLE:
            raise IndexError_("FAISS is not installed")

        vectors = np.array(embeddings, dtype=np.float32)
        dimension = vectors.shape[1]

        # Use flat L2 index for accuracy (suitable for <100k vectors)
        index = faiss.IndexFlatIP(dimension)  # Inner product for normalized vectors
        index.add(vectors)

        faiss.write_index(index, path)

    def load_faiss_index(self, repository_id: str):
        """Load a FAISS index for a repository."""
        if not FAISS_AVAILABLE:
            return None

        settings = get_settings()
        path = settings.indexes_path / repository_id / "faiss.index"
        if not path.exists():
            return None

        try:
            return faiss.read_index(str(path))
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            return None

    def load_bm25_index(self, repository_id: str) -> BM25Index | None:
        """Load a BM25 index for a repository."""
        settings = get_settings()
        path = settings.indexes_path / repository_id / "bm25.index"
        if not path.exists():
            return None

        try:
            return BM25Index.load(str(path))
        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            return None
