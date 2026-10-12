"""Evaluation API endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import EvaluationError, RepositoryNotFoundError
from app.core.logging import get_logger
from app.models.models import EvaluationRun, Repository, RepositoryStatus
from app.schemas.schemas import (
    EvaluationMetrics,
    EvaluationRequest,
    EvaluationResponse,
)
from app.services.evaluation.service import EvaluationService

logger = get_logger(__name__)
router = APIRouter()


@router.post("/run", response_model=EvaluationResponse)
async def run_evaluation(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Run retrieval evaluation."""
    repo = await db.get(Repository, request.repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {request.repository_id} not found")

    if repo.status != RepositoryStatus.READY:
        raise EvaluationError("Repository must be in READY state for evaluation")

    dataset_path = str(EvaluationService.resolve_dataset_path(request.dataset_path))

    eval_run = EvaluationRun(
        repository_id=request.repository_id,
        strategy=",".join(request.strategies),
        config={
            "dataset_path": dataset_path,
            "strategies": request.strategies,
        },
    )
    db.add(eval_run)
    await db.flush()
    # Background tasks may start before get_db commits at request teardown.
    await db.commit()

    background_tasks.add_task(
        EvaluationService.run_evaluation,
        eval_run.id,
        request.repository_id,
        request.strategies,
        dataset_path,
    )

    return EvaluationResponse(
        id=eval_run.id,
        repository_id=eval_run.repository_id,
        status=eval_run.status,
        created_at=eval_run.created_at,
        completed_at=eval_run.completed_at,
    )


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation results."""
    eval_run = await db.get(EvaluationRun, evaluation_id)
    if not eval_run:
        raise EvaluationError(f"Evaluation {evaluation_id} not found")

    return EvaluationResponse(
        id=eval_run.id,
        repository_id=eval_run.repository_id,
        status=eval_run.status,
        metrics=[
            EvaluationMetrics(
                strategy=result["strategy"],
                recall_at_5=result["recall_at_5"],
                recall_at_10=result["recall_at_10"],
                mrr=result["mrr"],
                avg_latency_ms=result["avg_latency_ms"],
                results=result["question_results"],
            )
            for result in (eval_run.results or [])
        ] if eval_run.status == "completed" else [],
        error_message=(eval_run.results or [{}])[0].get("error") if eval_run.status == "failed" else None,
        created_at=eval_run.created_at,
        completed_at=eval_run.completed_at,
    )
