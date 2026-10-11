"""Chat API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import RepositoryNotFoundError, RepositoryValidationError, SessionNotFoundError
from app.core.logging import get_logger
from app.models.models import ChatMessage, ChatSession, Repository, RepositoryFile, RepositoryStatus
from app.schemas.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    CodeContext,
    MessageResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
)
from app.services.generation.service import GenerationService

logger = get_logger(__name__)
router = APIRouter()


async def _resolve_code_context(
    repository: Repository, context: CodeContext, db: AsyncSession
) -> dict:
    """Resolve a selection from an indexed source file, never from client text."""
    if context.end_line < context.start_line:
        raise RepositoryValidationError("Selected code line range is invalid")

    file_result = await db.execute(
        select(RepositoryFile).where(
            RepositoryFile.repository_id == repository.id,
            RepositoryFile.path == context.file_path,
        )
    )
    if file_result.scalar_one_or_none() is None:
        raise RepositoryValidationError("Selected code file is not indexed in this repository")
    if not repository.storage_path:
        raise RepositoryValidationError("Repository storage not found")

    source_dir = (Path(repository.storage_path) / "source").resolve()
    source_path = (source_dir / context.file_path).resolve()
    if not source_path.is_relative_to(source_dir) or not source_path.is_file():
        raise RepositoryValidationError("Selected code file is unavailable")

    try:
        lines = source_path.read_text(encoding="utf-8", errors="replace").split("\n")
    except OSError as exc:
        raise RepositoryValidationError(f"Cannot read selected code file: {exc}") from exc
    if context.end_line > len(lines):
        raise RepositoryValidationError("Selected code line range exceeds the source file")

    return {
        "chunk_id": None,
        "file_path": context.file_path,
        "start_line": context.start_line,
        "end_line": context.end_line,
        "content": "\n".join(lines[context.start_line - 1:context.end_line]),
        "selected": True,
        "action": context.action,
    }


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

    code_context = (
        await _resolve_code_context(repo, request.code_context, db)
        if request.code_context else None
    )

    # Get or create session
    session = None
    if request.session_id:
        session = await db.get(ChatSession, request.session_id)
        if not session:
            raise SessionNotFoundError(f"Session {request.session_id} not found")
        if session.repository_id != request.repository_id:
            raise RepositoryValidationError("Chat session belongs to a different repository")

    if not session:
        session = ChatSession(
            repository_id=request.repository_id,
            tutor_mode=request.tutor_mode.value,
        )
    # Materialize history, then release the read transaction before slow model
    # work. In particular, never flush a user message while generation runs:
    # SQLite would hold its sole writer lock for the whole model request.
    history = []
    if request.session_id:
        history_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in history_result.scalars().all()
        ]
    await db.commit()

    # Generate answer
    gen_service = GenerationService()
    result = await gen_service.generate_answer(
        repository_id=request.repository_id,
        question=request.question,
        tutor_mode=request.tutor_mode.value,
        conversation_history=history,
        code_context=code_context,
    )

    # Persist the successful exchange in one short transaction. A session may
    # have been deleted while generation was running, so revalidate it first.
    if request.session_id:
        session = await db.get(ChatSession, request.session_id, populate_existing=True)
        if not session:
            raise SessionNotFoundError(f"Session {request.session_id} not found")
    else:
        db.add(session)
        await db.flush()
    session.tutor_mode = request.tutor_mode.value
    db.add(ChatMessage(session_id=session.id, role="user", content=request.question))

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
                retrieval_metadata=m.retrieval_metadata or {},
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
