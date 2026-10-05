"""Embedding service with provider abstraction."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

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


class SentenceTransformerProvider(EmbeddingProvider):
    """Embedding provider using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dimension = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                # Get dimension from a test encoding
                test = self._model.encode(["test"])
                self._dimension = len(test[0])
                logger.info(
                    f"Loaded embedding model: {self._model_name} "
                    f"(dim={self._dimension})"
                )
            except ImportError:
                raise EmbeddingProviderError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                raise EmbeddingProviderError(f"Failed to load model: {e}")

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents in batches."""
        self._load_model()

        if not texts:
            return []

        try:
            # Run embedding in thread pool to avoid blocking
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
            raise EmbeddingProviderError(f"Embedding failed: {e}")

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        self._load_model()

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
            raise EmbeddingProviderError(f"Query embedding failed: {e}")

    @property
    def dimension(self) -> int:
        self._load_model()
        return self._dimension

    @property
    def model_name(self) -> str:
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

        if provider_name == "sentence-transformers":
            self.provider = SentenceTransformerProvider(settings.embedding_model)
        elif provider_name == "ollama":
            self.provider = OllamaEmbeddingProvider(
                model_name=settings.embedding_model,
                base_url=settings.ollama_base_url,
            )
        else:
            # Default to sentence-transformers
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
