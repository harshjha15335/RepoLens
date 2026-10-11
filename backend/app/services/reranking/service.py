"""Reranking service with provider abstraction."""

from abc import ABC, abstractmethod
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Reranker(ABC):
    """Abstract reranker interface."""

    @abstractmethod
    async def rerank(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[dict]:
        """Rerank candidates by relevance to query."""
        pass


class CrossEncoderReranker(Reranker):
    """Cross-encoder reranker using sentence-transformers with resilient offline fallback."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None
        self._fallback_active = False

    def _load_model(self):
        if self._model is not None or self._fallback_active:
            return

        try:
            from sentence_transformers import CrossEncoder

            # Try local cache first
            try:
                self._model = CrossEncoder(self.model_name, local_files_only=True)
                logger.info(f"Loaded reranker model from local cache: {self.model_name}")
                return
            except Exception:
                pass

            self._model = CrossEncoder(self.model_name)
            logger.info(f"Loaded reranker model: {self.model_name}")
        except Exception as e:
            logger.warning(
                f"CrossEncoder download or load failed ({e}). "
                f"HuggingFace CDN (us.aws.cdn.hf.co) may be denied or blocked. "
                f"Falling back to pass-through/lexical reranking."
            )
            self._fallback_active = True

    async def rerank(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[dict]:
        """Rerank using cross-encoder scores or fallback to original order."""
        import asyncio

        self._load_model()

        if self._fallback_active or self._model is None or not candidates:
            return candidates[:top_k]

        try:
            pairs = [(query, c.get("content", "")) for c in candidates]
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None,
                lambda: self._model.predict(pairs),
            )

            # Attach scores and sort
            for i, score in enumerate(scores):
                candidates[i]["reranker_score"] = float(score)

            candidates.sort(key=lambda x: x.get("reranker_score", 0), reverse=True)
            return candidates[:top_k]
        except Exception as e:
            logger.warning(f"Reranking prediction failed ({e}), returning top candidates")
            return candidates[:top_k]


class NoopReranker(Reranker):
    """Pass-through reranker (disabled)."""

    async def rerank(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[dict]:
        return candidates[:top_k]


class RerankingService:
    """Reranking service using configured provider."""

    def __init__(self):
        settings = get_settings()
        provider = settings.reranker_provider.lower()

        if provider == "cross-encoder":
            self._reranker = CrossEncoderReranker(settings.reranker_model)
        else:
            self._reranker = NoopReranker()

    async def rerank(
        self, query: str, candidates: list[dict], top_k: int | None = None
    ) -> list[dict]:
        """Rerank candidates."""
        if top_k is None:
            top_k = get_settings().final_top_k
        return await self._reranker.rerank(query, candidates, top_k)
