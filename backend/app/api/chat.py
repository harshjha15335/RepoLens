"""Chat API endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.errors import RepositoryNotFoundError, SessionNotFoundError
from app.core.logging import get_logger
from app.models.models import Repository, ChatSession, ChatMessage, RepositoryStatus
from app.schemas.schemas import (
    ChatRequest, ChatResponse, SessionResponse, SessionListResponse,
    SessionDetailResponse, MessageResponse, Citation,
)
from app.services.generation.service import GenerationService

logger = get_logger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a question and get an AI-tutored answer."""
    # Verify repository exists and is ready
    repo = await db.get(Repository, request.repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {request.repository_id} not found")

    if repo.status != RepositoryStatus.READY:
        raise RepositoryNotFoundError(
            f"Repository is not ready for querying (status: {repo.status.value})"
        )

    # Get or create session
    session = None
    if request.session_id:
        session = await db.get(ChatSession, request.session_id)
        if not session:
            raise SessionNotFoundError(f"Session {request.session_id} not found")

    if not session:
        session = ChatSession(
            repository_id=request.repository_id,
            tutor_mode=request.tutor_mode.value,
        )
        db.add(session)
        await db.flush()

    # Get conversation history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    history = history_result.scalars().all()

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.question,
    )
    db.add(user_msg)
    await db.flush()

    # Generate answer
    gen_service = GenerationService()
    result = await gen_service.generate_answer(
        repository_id=request.repository_id,
        question=request.question,
        tutor_mode=request.tutor_mode.value,
        conversation_history=[
            {"role": m.role, "content": m.content} for m in history
        ],
    )

    # Save assistant message
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=result["answer"],
        citations=result.get("citations", []),
        retrieval_metadata=result.get("metadata", {}),
    )
    db.add(assistant_msg)

    # Update session title from first question
    if not session.title and len(history) == 0:
        session.title = request.question[:100]

    await db.flush()

    return ChatResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        answer=result["answer"],
        citations=[Citation(**c) for c in result.get("citations", [])],
        retrieval_metadata=result.get("metadata", {}),
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    repository_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List chat sessions."""
    query = select(ChatSession).order_by(ChatSession.updated_at.desc())
    if repository_id:
        query = query.where(ChatSession.repository_id == repository_id)

    result = await db.execute(query)
    sessions = result.scalars().all()

    session_responses = []
    for s in sessions:
        msg_count_result = await db.execute(
            select(func.count()).where(ChatMessage.session_id == s.id)
        )
        msg_count = msg_count_result.scalar() or 0

        session_responses.append(
            SessionResponse(
                id=s.id,
                repository_id=s.repository_id,
                title=s.title,
                tutor_mode=s.tutor_mode,
                message_count=msg_count,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )

    return SessionListResponse(sessions=session_responses, total=len(session_responses))


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    repository_id: str,
    tutor_mode: str = "developer",
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    session = ChatSession(
        repository_id=repository_id,
        tutor_mode=tutor_mode,
    )
    db.add(session)
    await db.flush()

    return SessionResponse(
        id=session.id,
        repository_id=session.repository_id,
        title=session.title,
        tutor_mode=session.tutor_mode,
        message_count=0,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get session with messages."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise SessionNotFoundError(f"Session {session_id} not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()

    return SessionDetailResponse(
        id=session.id,
        repository_id=session.repository_id,
        title=session.title,
        tutor_mode=session.tutor_mode,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=[Citation(**c) for c in (m.citations or [])],
                created_at=m.created_at,
            )
            for m in messages
        ],
        created_at=session.created_at,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a chat session."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise SessionNotFoundError(f"Session {session_id} not found")

    await db.delete(session)
    return {"message": f"Session {session_id} deleted"}
