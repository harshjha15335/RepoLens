"""API route definitions for CodeMentor-RAG."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.repositories import router as repositories_router
from app.api.chat import router as chat_router
from app.api.retrieval import router as retrieval_router
from app.api.evaluation import router as evaluation_router

router = APIRouter()

router.include_router(health_router, tags=["Health"])
router.include_router(repositories_router, prefix="/repositories", tags=["Repositories"])
router.include_router(chat_router, tags=["Chat"])
router.include_router(retrieval_router, prefix="/retrieval", tags=["Retrieval"])
router.include_router(evaluation_router, prefix="/evaluation", tags=["Evaluation"])
