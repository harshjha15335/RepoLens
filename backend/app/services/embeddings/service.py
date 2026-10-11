"""Embedding service with provider abstraction."""

import asyncio
from abc import ABC, abstractmethod

import numpy as np

from app.core.config import get_settings
from app.core.errors import EmbeddingProviderError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimension."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name."""
        pass


class DeterministicLocalEmbeddingProvider(EmbeddingProvider):
    """Offline, deterministic dense embedding provider (dim=384 default).

    Generates consistent, normalized dense vectors using code tokenization,
    identifier awareness, character n-grams, and signed hashing projections.
    Guarantees indexing succeeds without network access or when HF CDN is denied.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self._model_name = f"local-deterministic-{dimension}d"

    def _embed_text_sync(self, text: str) -> list[float]:
        if not text or not text.strip():
            vec = np.zeros(self._dimension, dtype=np.float32)
            vec[0] = 1.0
            return vec.tolist()

        import hashlib
        import re

        vec = np.zeros(self._dimension, dtype=np.float32)
        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*|[0-9]+", text)

        for token in tokens:
            lower = token.lower()
            h_bytes = hashlib.md5(lower.encode("utf-8")).digest()
            idx1 = int.from_bytes(h_bytes[:4], "little") % self._dimension
            idx2 = int.from_bytes(h_bytes[4:8], "little") % self._dimension
            sign1 = 1.0 if h_bytes[8] % 2 == 0 else -1.0
            sign2 = 1.0 if h_bytes[9] % 2 == 0 else -1.0

            weight = 2.0 if len(token) > 3 else 1.0
            vec[idx1] += sign1 * weight
            vec[idx2] += sign2 * (weight * 0.5)

            if len(lower) >= 3:
                for n in (3, 4):
                    for i in range(len(lower) - n + 1):
                        ngram = lower[i:i + n]
                        ng_h = hashlib.md5(ngram.encode("utf-8")).digest()
                        ng_idx = int.from_bytes(ng_h[:4], "little") % self._dimension
                        ng_sign = 1.0 if ng_h[4] % 2 == 0 else -1.0
                        vec[ng_idx] += ng_sign * 0.4

        norm = float(np.linalg.norm(vec))
        if norm > 1e-6:
            vec = vec / norm
        else:
            vec[0] = 1.0

        return vec.tolist()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: [self._embed_text_sync(t) for t in texts],
        )

    async def embed_query(self, text: str) -> list[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._embed_text_sync(text),
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name


class SentenceTransformerProvider(EmbeddingProvider):
    """Embedding provider using sentence-transformers with resilient local fallback."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dimension = None
        self._fallback_provider: DeterministicLocalEmbeddingProvider | None = None

    def _load_model(self):
        if self._model is not None or self._fallback_provider is not None:
            return

        target_dim = get_settings().embedding_dimension

        # 1. Try local cache first to avoid contacting HF CDN
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name, local_files_only=True)
            test = self._model.encode(["test"])
            self._dimension = len(test[0])
            logger.info(
                f"Loaded embedding model from local cache: {self._model_name} "
                f"(dim={self._dimension})"
            )
            return
        except Exception as e_cache:
            logger.debug(f"Local cache hit skipped for {self._model_name}: {e_cache}")

        # 2. Try online download/load with 5s timeout to prevent hanging if CDN is blocked
        import socket
        orig_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(5.0)
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            test = self._model.encode(["test"])
            self._dimension = len(test[0])
            logger.info(
                f"Loaded embedding model: {self._model_name} "
                f"(dim={self._dimension})"
            )
        except Exception as e:
            logger.warning(
                f"SentenceTransformer download or load failed ({e}). "
                f"CDN connection to us.aws.cdn.hf.co may be denied or blocked. "
                f"Falling back to built-in DeterministicLocalEmbeddingProvider (dim={target_dim})."
            )
            self._fallback_provider = DeterministicLocalEmbeddingProvider(dimension=target_dim)
            self._dimension = target_dim
        finally:
            socket.setdefaulttimeout(orig_timeout)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents in batches."""
        self._load_model()

        if self._fallback_provider is not None:
            return await self._fallback_provider.embed_documents(texts)

        if not texts:
            return []

        try:
            loop = asyncio.get_event_loop()
            batch_size = 64
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                embeddings = await loop.run_in_executor(
                    None,
                    lambda b=batch: self._model.encode(
                        b,
                        show_progress_bar=False,
                        normalize_embeddings=True,
                    ),
                )
                all_embeddings.extend(embeddings.tolist())
            return all_embeddings
        except Exception as e:
            logger.warning(f"Batch embedding failed ({e}), activating local fallback")
            self._fallback_provider = DeterministicLocalEmbeddingProvider(
                dimension=self._dimension or get_settings().embedding_dimension
            )
            return await self._fallback_provider.embed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        self._load_model()

        if self._fallback_provider is not None:
            return await self._fallback_provider.embed_query(text)

        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: self._model.encode(
                    text,
                    normalize_embeddings=True,
                ),
            )
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"Query embedding failed ({e}), activating local fallback")
            self._fallback_provider = DeterministicLocalEmbeddingProvider(
                dimension=self._dimension or get_settings().embedding_dimension
            )
            return await self._fallback_provider.embed_query(text)

    @property
    def dimension(self) -> int:
        self._load_model()
        return self._dimension or get_settings().embedding_dimension

    @property
    def model_name(self) -> str:
        if self._fallback_provider is not None:
            return self._fallback_provider.model_name
        return self._model_name


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Ollama."""

    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self._model_name = model_name
        self._base_url = base_url
        self._dimension = None

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            import httpx
            embeddings = []
            async with httpx.AsyncClient(timeout=120) as client:
                for text in texts:
                    resp = await client.post(
                        f"{self._base_url}/api/embeddings",
                        json={"model": self._model_name, "prompt": text},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    embeddings.append(data["embedding"])
                    if self._dimension is None:
                        self._dimension = len(data["embedding"])
            return embeddings
        except Exception as e:
            raise EmbeddingProviderError(f"Ollama embedding failed: {e}")

    async def embed_query(self, text: str) -> list[float]:
        result = await self.embed_documents([text])
        return result[0]

    @property
    def dimension(self) -> int:
        return self._dimension or 768

    @property
    def model_name(self) -> str:
        return self._model_name


class EmbeddingService:
    """Embedding service using configured provider."""

    def __init__(self):
        settings = get_settings()
        provider_name = settings.embedding_provider.lower()

        if provider_name in ("local", "offline", "deterministic", "fast", "hash"):
            self.provider = DeterministicLocalEmbeddingProvider(settings.embedding_dimension)
        elif provider_name == "sentence-transformers":
            self.provider = SentenceTransformerProvider(settings.embedding_model)
        elif provider_name == "ollama":
            self.provider = OllamaEmbeddingProvider(
                model_name=settings.embedding_model,
                base_url=settings.ollama_base_url,
            )
        else:
            # Default to sentence-transformers with fallback
            self.provider = SentenceTransformerProvider(settings.embedding_model)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        return await self.provider.embed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        return await self.provider.embed_query(text)

    @property
    def dimension(self) -> int:
        return self.provider.dimension

    @property
    def model_name(self) -> str:
        return self.provider.model_name
