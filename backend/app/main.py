"""FastAPI application entry point for CodeMentor-RAG."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.errors import CodeMentorError
from app.core.logging import setup_logging, get_logger, request_id_var, generate_request_id
from app.api.routes import router as api_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    setup_logging()
    settings = get_settings()
    logger.info("Starting CodeMentor-RAG backend")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Data directory: {settings.data_dir}")

    # Ensure data directories exist
    settings.data_path
    settings.repos_path
    settings.indexes_path

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    yield

    # Cleanup
    await close_db()
    logger.info("CodeMentor-RAG backend shut down")


app = FastAPI(
    title="CodeMentor-RAG",
    description="Retrieval-Augmented AI Tutor for Codebase Understanding",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
