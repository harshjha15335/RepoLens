"""Indexing service for FAISS dense index and BM25 lexical index."""

import json
import math
import re
from collections import Counter, OrderedDict

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
        self.documents: list[dict] = []
        self.inverted_index: dict[str, list[int]] = {}

    def build(self, chunks: list[dict]):
        """Build BM25 index from chunks."""
        self._build_documents([
            {"chunk_id": chunk.get("content_hash", ""), "tokens": self._tokenize(chunk)}
            for chunk in chunks
        ])

    def _build_documents(self, documents: list[dict]):
        """Derive all numeric index state from plain strings."""
        self.documents = documents
        self.n_docs = len(documents)
        self.doc_freqs = {}
        self.doc_lens = []
        self.tf = []
        self.chunk_ids = []
        self.inverted_index = {}

        for i, document in enumerate(documents):
            tokens = document["tokens"]
            self.chunk_ids.append(document["chunk_id"])

            tf = Counter(tokens)
            self.tf.append(dict(tf))
            self.doc_lens.append(len(tokens))

            for term in set(tokens):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
                if term not in self.inverted_index:
                    self.inverted_index[term] = []
                self.inverted_index[term].append(i)

        self.avg_dl = sum(self.doc_lens) / self.n_docs if self.n_docs > 0 else 0

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """Search the BM25 index. Returns (doc_index, score) tuples."""
        query_tokens = self._tokenize_query(query)

        candidate_docs = set()
        for term in query_tokens:
            if term in self.inverted_index:
                candidate_docs.update(self.inverted_index[term])

        scores = []
        for i in candidate_docs:
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
        """Save data-only JSON; numeric search state is rebuilt when loading."""
        data = {
            "version": 1,
            "k1": self.k1,
            "b": self.b,
            "documents": self.documents,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: str) -> "BM25Index":
        """Load validated JSON, never deserializing executable legacy artifacts."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
                raise ValueError("Unsupported BM25 format")
            k1, b = data["k1"], data["b"]
            if (type(k1) not in (int, float) or type(b) not in (int, float)
                    or not math.isfinite(k1) or not math.isfinite(b) or k1 <= 0 or not 0 <= b <= 1):
                raise ValueError("Invalid BM25 parameters")
            documents = data["documents"]
            if not isinstance(documents, list):
                raise ValueError("Invalid BM25 documents")
            for document in documents:
                if (not isinstance(document, dict) or not isinstance(document.get("chunk_id"), str)
                        or not isinstance(document.get("tokens"), list)
                        or any(not isinstance(token, str) for token in document["tokens"])):
                    raise ValueError("Invalid BM25 document strings")
        except (UnicodeError, ValueError, KeyError, TypeError, OverflowError, OSError) as exc:
            raise IndexError_("BM25 index uses an invalid or legacy format. Reindex this repository.") from exc
        index = cls(k1=k1, b=b)
        index._build_documents(documents)
        return index


class IndexingService:
    """Manages FAISS and BM25 indexes for repositories."""

    def __init__(self):
        self.settings = get_settings()
        self.cache_size = self.settings.index_cache_size
        self._faiss_cache: OrderedDict[str, any] = OrderedDict()
        self._bm25_cache: OrderedDict[str, BM25Index] = OrderedDict()
        self._metadata_cache: OrderedDict[str, dict] = OrderedDict()

    async def build_indexes(
        self,
        repository_id: str,
        chunks: list[dict],
        embeddings: list[list[float]],
        embedding_metadata: dict,
    ):
        """Build both FAISS and BM25 indexes."""
        # Invalidate cache for this repository
        self._faiss_cache.pop(repository_id, None)
        self._bm25_cache.pop(repository_id, None)
        self._metadata_cache.pop(repository_id, None)

        settings = get_settings()
        index_dir = settings.indexes_path / repository_id
        index_dir.mkdir(parents=True, exist_ok=True)

        self._validate_embedding_metadata(embedding_metadata)
        if (len(embeddings) != len(chunks)
                or any(len(vector) != embedding_metadata["dimension"] for vector in embeddings)):
            raise IndexError_("Embedding vectors do not match their provider metadata. Reindex this repository.")

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
            "embedding_model": embedding_metadata["model"],
            "embedding": embedding_metadata,
        }
        with open(str(index_dir / "metadata.json"), "w") as f:
            json.dump(metadata, f)

    @staticmethod
    def _validate_embedding_metadata(metadata: dict):
        if (not isinstance(metadata, dict)
                or any(not isinstance(metadata.get(key), str) or not metadata[key]
                       for key in ("provider", "model", "fingerprint"))
                or type(metadata.get("dimension")) is not int or metadata["dimension"] <= 0
                or type(metadata.get("version")) is not int or metadata["version"] != 1):
            raise IndexError_("Dense index embedding metadata is missing or invalid. Reindex this repository.")

    def load_embedding_metadata(self, repository_id: str) -> dict:
        """Read the actual indexed vector identity; legacy settings are insufficient."""
        if repository_id in self._metadata_cache:
            self._metadata_cache.move_to_end(repository_id)
            return self._metadata_cache[repository_id]

        path = get_settings().indexes_path / repository_id / "metadata.json"
        try:
            with open(path, encoding="utf-8") as file:
                metadata = json.load(file)["embedding"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise IndexError_("Dense index embedding metadata is missing or invalid. Reindex this repository.") from exc
        self._validate_embedding_metadata(metadata)

        # Cache the result
        self._metadata_cache[repository_id] = metadata
        self._metadata_cache.move_to_end(repository_id)
        if len(self._metadata_cache) > self.cache_size:
            self._metadata_cache.popitem(last=False)

        return metadata

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

        if repository_id in self._faiss_cache:
            self._faiss_cache.move_to_end(repository_id)
            return self._faiss_cache[repository_id]

        settings = get_settings()
        path = settings.indexes_path / repository_id / "faiss.index"
        if not path.exists():
            return None

        try:
            index = faiss.read_index(str(path))
            # Cache the result
            self._faiss_cache[repository_id] = index
            self._faiss_cache.move_to_end(repository_id)
            if len(self._faiss_cache) > self.cache_size:
                self._faiss_cache.popitem(last=False)
            return index
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            return None

    def load_bm25_index(self, repository_id: str) -> BM25Index | None:
        """Load a BM25 index for a repository."""
        if repository_id in self._bm25_cache:
            self._bm25_cache.move_to_end(repository_id)
            return self._bm25_cache[repository_id]

        settings = get_settings()
        path = settings.indexes_path / repository_id / "bm25.index"
        if not path.exists():
            return None

        try:
            index = BM25Index.load(str(path))
            # Cache the result
            self._bm25_cache[repository_id] = index
            self._bm25_cache.move_to_end(repository_id)
            if len(self._bm25_cache) > self.cache_size:
                self._bm25_cache.popitem(last=False)
            return index
        except IndexError_:
            raise
        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            return None
