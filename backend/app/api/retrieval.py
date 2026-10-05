"""Retrieval API endpoint for direct search queries."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import RepositoryNotFoundError
from app.core.logging import get_logger
from app.models.models import Repository, RepositoryStatus
from app.schemas.schemas import (
    RetrievalRequest, RetrievalResponse, RetrievedChunk,
)
from app.services.retrieval.service import RetrievalService

logger = get_logger(__name__)
router = APIRouter()


@router.post("/search", response_model=RetrievalResponse)
async def search_repository(
    request: RetrievalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search a repository using the retrieval pipeline."""
    repo = await db.get(Repository, request.repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {request.repository_id} not found")

    if repo.status != RepositoryStatus.READY:
        raise RepositoryNotFoundError(
            f"Repository is not ready for search (status: {repo.status.value})"
        )

    retrieval = RetrievalService()
    result = await retrieval.search(
        repository_id=request.repository_id,
        query=request.query,
        top_k=request.top_k,
        strategy=request.strategy,
        enable_graph_expansion=request.enable_graph_expansion,
        enable_mmr=request.enable_mmr,
        enable_reranking=request.enable_reranking,
    )

    return RetrievalResponse(
        query=request.query,
        intent=result.get("intent"),
        chunks=[RetrievedChunk(**c) for c in result.get("chunks", [])],
        total_retrieved=len(result.get("chunks", [])),
        latency_ms=result.get("latency_ms", 0),
        strategy=request.strategy,
    )
