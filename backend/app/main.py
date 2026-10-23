"""FastAPI application entry point for CodeMentor-RAG."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import update

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.database import close_db, get_session_factory, init_db
from app.core.errors import CodeMentorError
from app.core.logging import generate_request_id, get_logger, request_id_var, setup_logging
from app.core.security import SecurityMiddleware
from app.core.security import router as auth_router
from app.models.models import EvaluationRun, Repository, RepositoryStatus, utc_now

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    setup_logging()
    settings = get_settings()
    if len(settings.access_key) < 32:
        raise RuntimeError("Set REPOLENS_ACCESS_KEY to a random owner access key of at least 32 characters")
    logger.info("Starting CodeMentor-RAG backend")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Data directory: {settings.data_dir}")

    # Ensure data directories exist
    settings.data_path
    settings.repos_path
    settings.indexes_path

    # Initialize database
    await init_db()
    # Persisted repository state is the recovery record. A stopped worker must
    # not leave a job permanently active after this single worker restarts.
    await recover_interrupted_jobs()
    logger.info("Database initialized")

    # Pre-warm embedding service so user queries don't incur model load delay
    try:
        from app.services.embeddings.service import EmbeddingService
        await EmbeddingService().embed_query("warmup")
        logger.info("Embedding service pre-warmed")
    except Exception as e:
        logger.warning(f"Embedding pre-warm skipped: {e}")

    yield

    # Cleanup
    await close_db()
    logger.info("CodeMentor-RAG backend shut down")


async def recover_interrupted_jobs():
    """Make stopped work retryable without claiming it resumed automatically."""
    async with get_session_factory()() as db:
        await db.execute(update(Repository).where(Repository.status.not_in([
            RepositoryStatus.READY, RepositoryStatus.FAILED, RepositoryStatus.CANCELLED,
        ])).values(status=RepositoryStatus.FAILED,
                  progress_message="Indexing interrupted by server restart. Reindex to retry.",
                  error_message="Indexing worker stopped before completion"))
        await db.execute(update(EvaluationRun).where(
            EvaluationRun.status.in_(["pending", "running"]),
        ).values(status="failed", completed_at=utc_now(), results=[{
            "error": "Benchmark interrupted by server restart. Run it again to retry.",
        }]))
        await db.commit()


app = FastAPI(
    title="CodeMentor-RAG",
    description="Retrieval-Augmented AI Tutor for Codebase Understanding",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Browser requests use the frontend's same-origin proxy. Cross-origin browser
# API access is intentionally unavailable; native clients use the bearer key.
app.add_middleware(SecurityMiddleware)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add correlation request ID to all requests."""
    rid = generate_request_id()
    request_id_var.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(CodeMentorError)
async def codementor_error_handler(request: Request, exc: CodeMentorError):
    """Handle custom application errors."""
    status_map = {
        "RepositoryValidationError": 400,
        "ArchiveSecurityError": 400,
        "RepositoryNotFoundError": 404,
        "SessionNotFoundError": 404,
        "IngestionInProgressError": 409,
        "IndexError_": 409,
        "ParserError": 500,
        "EmbeddingProviderError": 503,
        "RetrievalError": 500,
        "GenerationProviderError": 503,
        "EvaluationError": 500,
    }
    status_code = status_map.get(type(exc).__name__, 500)
    logger.error(f"{type(exc).__name__}: {exc.message}", exc_info=exc if status_code >= 500 else None)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.message,
            "detail": exc.detail,
            "request_id": request_id_var.get(""),
        },
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.exception(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if get_settings().app_env == "development" else None,
            "request_id": request_id_var.get(""),
        },
    )


# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth", tags=["Owner access"])
