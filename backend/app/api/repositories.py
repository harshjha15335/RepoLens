"""Repository management API endpoints."""

import json
import re
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import (
    IngestionInProgressError,
    RepositoryNotFoundError,
    RepositoryValidationError,
)
from app.core.logging import get_logger
from app.models.models import (
    Chunk,
    GraphEdge,
    GraphNode,
    Repository,
    RepositoryFile,
    RepositoryStatus,
)
from app.schemas.schemas import (
    FileContentResponse,
    FileInfo,
    GitImportRequest,
    RepositoryListResponse,
    RepositoryResponse,
    RepositoryStats,
    SymbolInfo,
    SymbolListResponse,
)
from app.services.artifact_store import (
    GIT_METADATA,
    SOURCE_ZIP,
    ensure_git_metadata,
    ensure_source,
    ensure_upload,
    save_file,
)
from app.services.ingestion.service import IngestionService, validate_git_url

logger = get_logger(__name__)
router = APIRouter()
GIT_SOURCE_METADATA_FILE = "source.json"
_queued_ingestions: set[str] = set()


async def _run_queued_ingestion(
    repository_id: str, source: str, source_type: str, branch: str | None = None
):
    """Release the in-process queue guard after the worker finishes."""
    try:
        await IngestionService.run_ingestion(repository_id, source, source_type, branch)
    finally:
        _queued_ingestions.discard(repository_id)


def _queue_ingestion(
    background_tasks: BackgroundTasks,
    repository_id: str,
    source: str,
    source_type: str,
    branch: str | None = None,
):
    _queued_ingestions.add(repository_id)
    background_tasks.add_task(_run_queued_ingestion, repository_id, source, source_type, branch)


def _repo_to_response(repo: Repository) -> RepositoryResponse:
    """Convert a Repository model to API response."""
    return RepositoryResponse(
        id=repo.id,
        name=repo.name,
        source_type=repo.source_type,
        status=repo.status,
        progress=repo.progress or 0,
        progress_message=repo.progress_message,
        error_message=repo.error_message,
        languages=repo.languages or [],
        stats=RepositoryStats(
            files=repo.file_count or 0,
            chunks=repo.chunk_count or 0,
            symbols=repo.symbol_count or 0,
            graph_nodes=repo.graph_node_count or 0,
            graph_edges=repo.graph_edge_count or 0,
        ),
        created_at=repo.created_at,
        updated_at=repo.updated_at,
        indexed_at=repo.indexed_at,
    )


@router.post("/upload", response_model=RepositoryResponse)
async def upload_repository(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload a ZIP repository for analysis."""
    if background_tasks is None:
        background_tasks = BackgroundTasks()
    settings = get_settings()

    # Validate file type
    if not file.filename or not file.filename.endswith(".zip"):
        raise RepositoryValidationError("Only ZIP files are supported")

    staged_path = None
    repo_dir = None
    try:
        # Read no more than one fixed-size chunk into application memory.
        with tempfile.NamedTemporaryFile(dir=settings.repos_path, prefix="upload-", delete=False) as staged:
            staged_path = Path(staged.name)
            total_bytes = 0
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_bytes:
                    raise RepositoryValidationError(
                        f"File exceeds maximum upload size of {settings.max_upload_mb}MB"
                    )
                staged.write(chunk)

        repo = Repository(name=Path(file.filename).stem, source_type="zip", status=RepositoryStatus.PENDING)
        db.add(repo)
        await db.flush()
        repo_dir = settings.repos_path / repo.id
        repo_dir.mkdir(parents=True, exist_ok=True)
        zip_path = repo_dir / "source.zip"
        staged_path.replace(zip_path)
        repo.storage_path = str(repo_dir)
        # A queued worker may start on another instance or after this disk is lost.
        await save_file(db, repo.id, SOURCE_ZIP, zip_path)
        # Workers use a separate session and require a committed record.
        await db.commit()
    except BaseException:
        await db.rollback()
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
        if repo_dir is not None:
            shutil.rmtree(repo_dir, ignore_errors=True)
        raise
    finally:
        await file.close()

    logger.info(f"Repository uploaded: {repo.name} ({repo.id})")

    # Start ingestion in background
    _queue_ingestion(
        background_tasks,
        repo.id,
        str(zip_path),
        "zip",
    )

    return _repo_to_response(repo)


@router.post("/git", response_model=RepositoryResponse)
async def import_git_repository(
    request: GitImportRequest,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """Import a Git repository by URL."""
    if background_tasks is None:
        background_tasks = BackgroundTasks()
    url = await validate_git_url(request.url)
    if request.branch is not None and (
        not request.branch.strip() or request.branch.startswith("-")
    ):
        raise RepositoryValidationError("Invalid Git branch")

    # Extract repo name from URL
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")

    repo = Repository(
        name=repo_name,
        source_type="git",
        source_url=url,
        status=RepositoryStatus.PENDING,
    )
    db.add(repo)
    await db.flush()

    settings = get_settings()
    repo_dir = settings.repos_path / repo.id
    repo_dir.mkdir(parents=True, exist_ok=True)
    repo.storage_path = str(repo_dir)
    (repo_dir / GIT_SOURCE_METADATA_FILE).write_text(
        json.dumps({"branch": request.branch}), encoding="utf-8"
    )
    await save_file(db, repo.id, GIT_METADATA, repo_dir / GIT_SOURCE_METADATA_FILE)
    await db.commit()

    logger.info(f"Git repository import started: {repo.name} ({repo.id})")

    _queue_ingestion(
        background_tasks,
        repo.id,
        url,
        "git",
        request.branch,
    )

    return _repo_to_response(repo)


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(db: AsyncSession = Depends(get_db)):
    """List all repositories."""
    result = await db.execute(
        select(Repository).order_by(Repository.created_at.desc())
    )
    repos = result.scalars().all()
    return RepositoryListResponse(
        repositories=[_repo_to_response(r) for r in repos],
        total=len(repos),
    )


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(repository_id: str, db: AsyncSession = Depends(get_db)):
    """Get repository details."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")
    return _repo_to_response(repo)


@router.delete("/{repository_id}")
async def delete_repository(repository_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a repository and all associated data."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    settings = get_settings()
    storage_dir = Path(repo.storage_path).resolve() if repo.storage_path else None
    storage_root = settings.repos_path.resolve()
    if storage_dir and (storage_dir == storage_root or not storage_dir.is_relative_to(storage_root)):
        raise RepositoryValidationError("Repository storage must be inside application storage")
    index_root = settings.indexes_path.resolve()
    index_dir = (index_root / repository_id).resolve()
    if index_dir == index_root or not index_dir.is_relative_to(index_root):
        raise RepositoryValidationError("Invalid repository index path")

    await db.delete(repo)
    # Commit before responding so the next request cannot see a deleted record.
    await db.commit()
    if storage_dir and storage_dir.exists():
        shutil.rmtree(storage_dir, ignore_errors=True)
    if index_dir.exists():
        shutil.rmtree(index_dir, ignore_errors=True)
    logger.info(f"Repository deleted: {repo.name} ({repo.id})")

    return {"message": f"Repository {repository_id} deleted"}


@router.post("/{repository_id}/index", response_model=RepositoryResponse)
async def reindex_repository(
    repository_id: str,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """Trigger re-indexing of a repository."""
    if background_tasks is None:
        background_tasks = BackgroundTasks()
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    if repository_id in _queued_ingestions or repo.status in (
        RepositoryStatus.DISCOVERING,
        RepositoryStatus.PARSING,
        RepositoryStatus.CHUNKING,
        RepositoryStatus.BUILDING_GRAPH,
        RepositoryStatus.EMBEDDING,
        RepositoryStatus.INDEXING,
    ):
        raise IngestionInProgressError("Ingestion is already in progress")

    source = repo.source_url or str(repo.storage_path)
    source_type = repo.source_type
    if source_type == "zip":
        await ensure_upload(db, repo)
        source = str(Path(repo.storage_path) / "source.zip")
        if not Path(source).is_file():
            await ensure_source(db, repo)
            if not (Path(repo.storage_path) / "source").is_dir():
                raise RepositoryValidationError("Repository source is unavailable for reindexing")
            source_type = "local"
            source = str(Path(repo.storage_path) / "source")
    branch = None
    if source_type == "git":
        await ensure_git_metadata(db, repo)
        metadata_file = Path(repo.storage_path) / GIT_SOURCE_METADATA_FILE
        if metadata_file.exists():
            branch = json.loads(metadata_file.read_text(encoding="utf-8")).get("branch")
        else:
            # Repositories imported before branch metadata was introduced.
            head_file = Path(repo.storage_path) / "source" / ".git" / "HEAD"
            if head_file.exists():
                head = head_file.read_text(encoding="utf-8").strip()
                if head.startswith("ref: refs/heads/"):
                    branch = head.removeprefix("ref: refs/heads/")

    # Reserve this worker before yielding at commit. Persisted PENDING records
    # without a live in-process worker remain retryable after a server restart.
    _queued_ingestions.add(repository_id)
    try:
        repo.status = RepositoryStatus.PENDING
        repo.progress = 0
        repo.error_message = None
        repo.progress_message = "Queued for indexing"
        await db.commit()
        _queue_ingestion(background_tasks, repo.id, source, source_type, branch)
    except Exception:
        _queued_ingestions.discard(repository_id)
        raise

    return _repo_to_response(repo)


@router.get("/{repository_id}/status", response_model=RepositoryResponse)
async def get_repository_status(
    repository_id: str, db: AsyncSession = Depends(get_db)
):
    """Get repository indexing status."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")
    return _repo_to_response(repo)


@router.get("/{repository_id}/files", response_model=list[FileInfo])
async def list_repository_files(
    repository_id: str, db: AsyncSession = Depends(get_db)
):
    """List all files in a repository."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    result = await db.execute(
        select(RepositoryFile)
        .where(RepositoryFile.repository_id == repository_id)
        .order_by(RepositoryFile.path)
    )
    files = result.scalars().all()
    return [
        FileInfo(
            id=f.id,
            path=f.path,
            language=f.language,
            size_bytes=f.size_bytes,
            symbol_count=f.symbol_count,
            chunk_count=f.chunk_count,
        )
        for f in files
    ]


@router.get("/{repository_id}/files/content", response_model=FileContentResponse)
async def get_file_content(
    repository_id: str,
    path: str = Query(..., description="File path within the repository"),
    db: AsyncSession = Depends(get_db),
):
    """Get the content of a specific file."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    if not repo.storage_path:
        raise RepositoryValidationError("Repository storage not found")

    await ensure_source(db, repo)

    # Security: validate path doesn't escape repository
    source_dir = (Path(repo.storage_path) / "source").resolve()
    full_path = (source_dir / path).resolve()
    try:
        full_path.relative_to(source_dir)
    except ValueError:
        raise RepositoryValidationError("Invalid file path")

    result = await db.execute(
        select(RepositoryFile).where(
            RepositoryFile.repository_id == repository_id,
            RepositoryFile.path == path,
        )
    )
    file_record = result.scalar_one_or_none()
    if not file_record or not full_path.is_file():
        raise RepositoryNotFoundError(f"File not found: {path}")

    try:
        with full_path.open("r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        raise RepositoryValidationError(f"Cannot read file: {str(e)}")

    lines = content.count("\n") + 1

    # Detect language
    return FileContentResponse(
        path=path,
        content=content,
        language=file_record.language if file_record else None,
        total_lines=lines,
    )


@router.get("/{repository_id}/symbols", response_model=SymbolListResponse)
async def list_repository_symbols(
    repository_id: str,
    symbol_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List symbols in a repository."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    query = select(Chunk).where(
        Chunk.repository_id == repository_id,
        Chunk.symbol_name.isnot(None),
    )
    if symbol_type:
        query = query.where(Chunk.symbol_type == symbol_type)

    result = await db.execute(query.order_by(Chunk.file_path, Chunk.start_line))
    chunks = result.scalars().all()

    # Deduplicate symbols
    seen = set()
    symbols = []
    for c in chunks:
        key = (c.symbol_name, c.file_path, c.start_line)
        if key not in seen:
            seen.add(key)
            symbols.append(
                SymbolInfo(
                    name=c.symbol_name,
                    symbol_type=c.symbol_type or "unknown",
                    file_path=c.file_path,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    parent_symbol=c.parent_symbol,
                )
            )

    return SymbolListResponse(symbols=symbols, total=len(symbols))


@router.get("/{repository_id}/graph")
async def get_repository_graph(
    repository_id: str,
    node_type: Optional[str] = None,
    relationship_type: Optional[str] = None,
    limit: int = Query(default=150, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get the code knowledge graph (nodes and edges) for a repository."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    # Fetch nodes
    node_query = select(GraphNode).where(GraphNode.repository_id == repository_id)
    if node_type:
        node_query = node_query.where(GraphNode.node_type == node_type)
    node_query = node_query.limit(limit)

    node_res = await db.execute(node_query)
    nodes = node_res.scalars().all()
    node_ids = {n.id for n in nodes}

    # Fetch edges connected to these nodes
    edge_query = select(GraphEdge).where(
        GraphEdge.repository_id == repository_id,
        GraphEdge.source_id.in_(node_ids),
        GraphEdge.target_id.in_(node_ids),
    )
    if relationship_type:
        edge_query = edge_query.where(GraphEdge.relationship_type == relationship_type)

    edge_res = await db.execute(edge_query)
    edges = edge_res.scalars().all()

    # Calculate statistics
    node_type_counts = {}
    for n in nodes:
        node_type_counts[n.node_type] = node_type_counts.get(n.node_type, 0) + 1

    edge_type_counts = {}
    for e in edges:
        edge_type_counts[e.relationship_type] = edge_type_counts.get(e.relationship_type, 0) + 1

    return {
        "repository_id": repository_id,
        "nodes": [
            {
                "id": n.id,
                "type": n.node_type,
                "name": n.name,
                "qualified_name": n.qualified_name or n.name,
                "file_path": n.file_path,
                "start_line": n.start_line,
                "end_line": n.end_line,
                "metadata": n.metadata_ or {},
            }
            for n in nodes
        ],
        "edges": [
            {
                "id": e.id,
                "source": e.source_id,
                "target": e.target_id,
                "type": e.relationship_type,
                "metadata": e.metadata_ or {},
            }
            for e in edges
        ],
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": node_type_counts,
            "edge_types": edge_type_counts,
        },
    }


@router.get("/{repository_id}/call-flows")
async def get_repository_call_flows(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get structured call flow relationships (caller -> callee and inheritance) for a repository."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    # Get nodes and mapping
    node_res = await db.execute(
        select(GraphNode).where(GraphNode.repository_id == repository_id)
    )
    nodes = {n.id: n for n in node_res.scalars().all()}

    # Get CALLS and INHERITS edges
    edge_res = await db.execute(
        select(GraphEdge).where(
            GraphEdge.repository_id == repository_id,
            GraphEdge.relationship_type.in_(["CALLS", "INHERITS"]),
        )
    )
    edges = edge_res.scalars().all()

    flows = []
    for e in edges:
        src = nodes.get(e.source_id)
        tgt = nodes.get(e.target_id)
        if src and tgt:
            flows.append({
                "id": e.id,
                "relationship": e.relationship_type,
                "caller": {
                    "name": src.name,
                    "type": src.node_type,
                    "file_path": src.file_path,
                    "start_line": src.start_line,
                    "end_line": src.end_line,
                },
                "callee": {
                    "name": tgt.name,
                    "type": tgt.node_type,
                    "file_path": tgt.file_path,
                    "start_line": tgt.start_line,
                    "end_line": tgt.end_line,
                },
            })

    return {
        "repository_id": repository_id,
        "flows": flows,
        "total": len(flows),
    }


@router.post("/{repository_id}/interview/generate")
async def generate_interview_questions(
    repository_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """Generate technical interview questions grounded in the repository's AST and architecture."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    difficulty = request.get("difficulty", "intermediate")
    focus = request.get("focus", "general")
    count = request.get("count", 5)
    if difficulty not in {"beginner", "intermediate", "advanced"}:
        raise RepositoryValidationError("Invalid interview difficulty")
    if focus not in {"general", "architecture", "backend", "frontend", "algorithms", "data flow"}:
        raise RepositoryValidationError("Invalid interview focus")
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 15:
        raise RepositoryValidationError("Interview question count must be between 1 and 15")

    # Fetch symbols for repository
    sym_res = await db.execute(
        select(Chunk).where(
            Chunk.repository_id == repository_id,
            Chunk.symbol_name.isnot(None),
        ).order_by(Chunk.file_path, Chunk.start_line)
    )
    # Large symbols are split into chunks with display suffixes such as
    # "ExpressionParser (part 1)". Interview questions target real symbols.
    seen_symbols = set()
    symbols = []
    for chunk in sym_res.scalars():
        name = re.sub(r" \(part \d+\)$", "", chunk.symbol_name)
        key = (chunk.file_path, chunk.symbol_type, name)
        if key in seen_symbols:
            continue
        seen_symbols.add(key)
        symbols.append(SimpleNamespace(
            symbol_name=name,
            symbol_type=chunk.symbol_type,
            file_path=chunk.file_path,
            start_line=chunk.start_line,
        ))
    if focus == "backend":
        symbols = [s for s in symbols if "backend" in s.file_path.lower() or s.file_path.endswith(".py")]
    elif focus == "frontend":
        symbols = [s for s in symbols if "frontend" in s.file_path.lower() or s.file_path.endswith((".tsx", ".jsx", ".ts", ".js"))]

    # Build grounded repository questions based on discovered architecture
    questions = []
    classes = [s for s in symbols if s.symbol_type == "class"]
    functions = [s for s in symbols if s.symbol_type in ("function", "method")]

    # Question generator templates grounded in real code
    if classes:
        main_class = classes[0]
        questions.append({
            "id": "int-q-1",
            "topic": "Architecture & Object Model",
            "difficulty": difficulty,
            "question": f"Explain the role of `{main_class.symbol_name}` in `{main_class.file_path}`. What does its source show about its responsibilities?",
            "target_files": [main_class.file_path],
            "target_symbols": [main_class.symbol_name],
            "expected_concepts": ["class structure", "source-backed responsibilities"],
        })

    inheritance_res = await db.execute(
        select(GraphEdge).where(
            GraphEdge.repository_id == repository_id,
            GraphEdge.relationship_type == "INHERITS",
        )
    )
    inheritance_edges = inheritance_res.scalars().all()
    if inheritance_edges:
        edge = inheritance_edges[0]
        derived_class = await db.get(GraphNode, edge.source_id)
        base_class = await db.get(GraphNode, edge.target_id)
        if derived_class and base_class and (
            focus not in {"backend", "frontend"}
            or any(s.file_path == derived_class.file_path for s in symbols)
        ):
            questions.append({
                "id": "int-q-2",
                "topic": "Inheritance & Extensibility",
                "difficulty": difficulty,
                "question": f"How does `{derived_class.name}` relate to `{base_class.name}`? Explain the inheritance shown in the source.",
                "target_files": [derived_class.file_path, base_class.file_path],
                "target_symbols": [derived_class.name, base_class.name],
                "expected_concepts": ["inheritance relationship", "class implementation"],
            })

    # Method / algorithmic question
    call_methods = [f for f in functions if f.symbol_name and ("parse" in f.symbol_name.lower() or "token" in f.symbol_name.lower() or "calc" in f.symbol_name.lower() or "eval" in f.symbol_name.lower())]
    if call_methods:
        cm = call_methods[0]
        questions.append({
            "id": "int-q-3",
            "topic": "Algorithms & Parsing",
            "difficulty": difficulty,
            "question": f"Describe the logic inside `{cm.symbol_name}` ({cm.file_path}:L{cm.start_line}). Which inputs and branches are visible in its implementation?",
            "target_files": [cm.file_path],
            "target_symbols": [cm.symbol_name],
            "expected_concepts": ["input parsing", "validation", "control flow"],
        })

    # Error handling question
    error_methods = [f for f in functions if f.symbol_name and ("divide" in f.symbol_name.lower() or "err" in f.symbol_name.lower() or "check" in f.symbol_name.lower())]
    if error_methods:
        em = error_methods[0]
        questions.append({
            "id": "int-q-4",
            "topic": "Error Handling & Edge Cases",
            "difficulty": difficulty,
            "question": f"Which edge cases, if any, are handled by `{em.symbol_name}` in `{em.file_path}`? Point to the relevant branches.",
            "target_files": [em.file_path],
            "target_symbols": [em.symbol_name],
            "expected_concepts": ["exception propagation", "defensive programming", "edge conditions"],
        })

    # State & tracking question
    history_methods = [f for f in functions if f.symbol_name and ("record" in f.symbol_name.lower() or "history" in f.symbol_name.lower() or "log" in f.symbol_name.lower())]
    if history_methods:
        hm = history_methods[0]
        questions.append({
            "id": "int-q-5",
            "topic": "Data Flow & State Tracking",
            "difficulty": difficulty,
            "question": f"Trace the implementation of `{hm.symbol_name}`. What state, if any, does it change?",
            "target_files": [hm.file_path],
            "target_symbols": [hm.symbol_name],
            "expected_concepts": ["data flow", "mutation", "caller dependencies"],
        })

    # Fallbacks if repository has different symbols
    if len(questions) < count:
        used = {(symbol, path) for question in questions for symbol, path in zip(question["target_symbols"], question["target_files"])}
        candidates = [s for s in symbols if (s.symbol_name, s.file_path) not in used]
        if focus == "architecture":
            candidates.sort(key=lambda s: s.symbol_type not in ("class", "interface"))
        elif focus == "algorithms":
            candidates.sort(key=lambda s: s.symbol_type not in ("function", "method"))
        elif focus == "data flow":
            candidates.sort(key=lambda s: not any(k in s.symbol_name.lower() for k in ("flow", "process", "handle", "load", "save", "update")))
        for idx, sym in enumerate(candidates[:count - len(questions)]):
            questions.append({
                "id": f"int-q-extra-{idx}",
                "topic": "Implementation Details",
                "difficulty": difficulty,
                "question": f"Walk through the implementation of `{sym.symbol_name}` in `{sym.file_path}`. Which behavior can you verify from the source?",
                "target_files": [sym.file_path],
                "target_symbols": [sym.symbol_name],
                "expected_concepts": ["signature", "logic", "efficiency"],
            })

    focus_topics = {
        "architecture": {"Architecture & Object Model", "Inheritance & Extensibility"},
        "algorithms": {"Algorithms & Parsing", "Implementation Details"},
        "data flow": {"Data Flow & State Tracking"},
    }
    preferred_topics = focus_topics.get(focus, set())
    questions.sort(key=lambda item: item["topic"] not in preferred_topics)
    difficulty_prompt = {
        "beginner": "Explain in plain language. ",
        "intermediate": "Use source examples. ",
        "advanced": "Analyze the relevant branches and tradeoffs shown in the source. ",
    }[difficulty]
    for item in questions:
        item["question"] = difficulty_prompt + item["question"]

    return {
        "repository_id": repository_id,
        "difficulty": difficulty,
        "focus": focus,
        "questions": questions[:count],
        "total": len(questions[:count]),
    }


@router.post("/{repository_id}/interview/evaluate")
async def evaluate_interview_answer(
    repository_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """Evaluate user interview response against repository ground truth code evidence."""
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise RepositoryNotFoundError(f"Repository {repository_id} not found")

    question = request.get("question", "")
    user_answer = request.get("user_answer", "")
    target_symbols = request.get("target_symbols", [])
    target_files = request.get("target_files", [])
    if not isinstance(question, str) or not isinstance(user_answer, str):
        raise RepositoryValidationError("Question and answer must be text")
    if not isinstance(target_symbols, list) or any(not isinstance(s, str) for s in target_symbols):
        raise RepositoryValidationError("Target symbols must be a list of names")
    if not isinstance(target_files, list) or any(not isinstance(path, str) for path in target_files):
        raise RepositoryValidationError("Target files must be a list of paths")
    user_answer = user_answer.strip()

    if not user_answer:
        return {
            "score": 0,
            "what_was_correct": "No answer provided.",
            "what_was_missing": "Please provide an explanation of the requested implementation.",
            "grounded_explanation": "Answers must be grounded in the repository code.",
            "citations": [],
        }

    # Generated questions already identify their source. Prefer that evidence
    # over generic retrieval, which can rank unrelated import blocks first.
    chunks = []
    if target_files:
        source_query = select(Chunk).where(
            Chunk.repository_id == repository_id,
            Chunk.file_path.in_(target_files),
        ).order_by(Chunk.chunk_index)
        source_chunks = (await db.execute(source_query)).scalars().all()
        if target_symbols:
            source_chunks = [chunk for chunk in source_chunks if
                re.sub(r"\s*\(part \d+\)$", "", chunk.symbol_name or "") in target_symbols]
        chunks = [{
            "file_path": chunk.file_path, "start_line": chunk.start_line,
            "end_line": chunk.end_line, "symbol_name": chunk.symbol_name,
            "content": chunk.content,
        } for chunk in source_chunks]
    if not chunks:
        from app.services.retrieval.service import RetrievalService
        search_res = await RetrievalService().search(
            repository_id=repository_id,
            query=f"{question} {' '.join(target_symbols)}",
            top_k=5,
            strategy="hybrid_rrf",
        )
        chunks = search_res.get("chunks", [])
    citations = [
        {
            "file_path": c["file_path"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "symbol_name": c.get("symbol_name"),
            "snippet": c.get("content", "")[:180],
        }
        for c in chunks[:3]
    ]

    # This is an evidence overlap check, not a semantic correctness judgment.
    evidence_tokens = {
        token.lower()
        for chunk in chunks
        for token in re.findall(r"[A-Za-z_]\w{3,}", chunk.get("content", ""))
        if token.lower() not in {"self", "return", "true", "false", "none", "class", "function", "const"}
    }
    answer_tokens = {token.lower() for token in re.findall(r"[A-Za-z_]\w{3,}", user_answer)}
    matching_tokens = sorted(answer_tokens & evidence_tokens)
    mentioned_symbols = [s for s in target_symbols if s.lower() in user_answer.lower()]
    score = min(75, len(matching_tokens) * 10) + (25 if mentioned_symbols else 0)
    if not chunks:
        score = 0

    if matching_tokens:
        correct = f"Your answer uses terms found in the retrieved source: {', '.join(matching_tokens[:6])}."
    else:
        correct = "I could not match your explanation to the retrieved source."
    missing = "Compare your claims with the cited code. This automated check cannot verify whether your reasoning is correct."
    explanation = "Relevant source excerpts: " + "; ".join(
        f"{c['file_path']}:L{c['start_line']}-{c['end_line']} — {c['snippet']}"
        for c in citations
    ) if citations else "No relevant indexed source was retrieved for this question."

    return {
        "score": score,
        "what_was_correct": correct,
        "what_was_missing": missing,
        "grounded_explanation": explanation,
        "citations": citations,
    }

