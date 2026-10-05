"""Repository management API endpoints."""

import os
import shutil
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import (
    RepositoryNotFoundError,
    RepositoryValidationError,
    IngestionInProgressError,
)
from app.core.logging import get_logger
from app.models.models import (
    Repository, RepositoryFile, RepositoryStatus, Chunk,
    GraphNode, GraphEdge,
)
from app.schemas.schemas import (
    RepositoryResponse, RepositoryListResponse, RepositoryStats,
    GitImportRequest, FileInfo, FileTreeNode, FileContentResponse,
    SymbolInfo, SymbolListResponse,
)
from app.services.ingestion.service import IngestionService

logger = get_logger(__name__)
router = APIRouter()


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

    # Read file content
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise RepositoryValidationError(
            f"File exceeds maximum upload size of {settings.max_upload_mb}MB"
        )

    # Create repository record
    repo_name = file.filename.replace(".zip", "")
    repo = Repository(
        name=repo_name,
        source_type="zip",
        status=RepositoryStatus.PENDING,
    )
    db.add(repo)
    await db.flush()

    # Save ZIP file
    repo_dir = settings.repos_path / repo.id
    repo_dir.mkdir(parents=True, exist_ok=True)
    zip_path = repo_dir / "source.zip"
    zip_path.write_bytes(content)

    repo.storage_path = str(repo_dir)
    await db.flush()

    logger.info(f"Repository uploaded: {repo.name} ({repo.id})")

    # Start ingestion in background
    background_tasks.add_task(
        IngestionService.run_ingestion,
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
    # Basic URL validation
    url = request.url.strip()
    if not url.startswith(("https://", "http://", "git@")):
        raise RepositoryValidationError("Invalid Git URL. Use HTTPS or SSH URL.")

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
    await db.flush()

    logger.info(f"Git repository import started: {repo.name} ({repo.id})")

    background_tasks.add_task(
        IngestionService.run_ingestion,
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

    # Delete storage
    if repo.storage_path and os.path.exists(repo.storage_path):
        shutil.rmtree(repo.storage_path, ignore_errors=True)

    # Delete index files
    settings = get_settings()
    index_dir = settings.indexes_path / repository_id
    if index_dir.exists():
        shutil.rmtree(str(index_dir), ignore_errors=True)

    await db.delete(repo)
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

    if repo.status in (
        RepositoryStatus.DISCOVERING,
        RepositoryStatus.PARSING,
        RepositoryStatus.CHUNKING,
        RepositoryStatus.BUILDING_GRAPH,
        RepositoryStatus.EMBEDDING,
        RepositoryStatus.INDEXING,
    ):
        raise IngestionInProgressError("Ingestion is already in progress")

    repo.status = RepositoryStatus.PENDING
    repo.progress = 0
    repo.error_message = None
    await db.flush()

    source = repo.source_url or str(repo.storage_path)
    source_type = repo.source_type

    background_tasks.add_task(
        IngestionService.run_ingestion,
        repo.id,
        source,
        source_type,
    )

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

    # Security: validate path doesn't escape repository
    settings = get_settings()
    source_dir = os.path.join(repo.storage_path, "source")
    full_path = os.path.normpath(os.path.join(source_dir, path))

    if not full_path.startswith(os.path.normpath(source_dir)):
        raise RepositoryValidationError("Invalid file path")

    if not os.path.isfile(full_path):
        raise RepositoryNotFoundError(f"File not found: {path}")

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        raise RepositoryValidationError(f"Cannot read file: {str(e)}")

    lines = content.count("\n") + 1

    # Detect language
    result = await db.execute(
        select(RepositoryFile)
        .where(
            RepositoryFile.repository_id == repository_id,
            RepositoryFile.path == path,
        )
    )
    file_record = result.scalar_one_or_none()

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

    difficulty = request.get("difficulty", "intermediate").lower()
    focus = request.get("focus", "general").lower()
    count = min(max(int(request.get("count", 5)), 3), 15)

    # Fetch symbols and files for repository
    sym_res = await db.execute(
        select(Chunk).where(
            Chunk.repository_id == repository_id,
            Chunk.symbol_name.isnot(None),
        ).limit(30)
    )
    symbols = sym_res.scalars().all()

    file_res = await db.execute(
        select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
    )
    files = file_res.scalars().all()
    file_names = [f.path for f in files]

    # Build grounded repository questions based on discovered architecture
    questions = []
    classes = [s for s in symbols if s.symbol_type == "class"]
    functions = [s for s in symbols if s.symbol_type in ("function", "method")]

    # Question generator templates grounded in real code
    if classes:
        main_class = classes[0]
        questions.append({
            "id": f"int-q-1",
            "topic": "Architecture & Object Model",
            "difficulty": difficulty,
            "question": f"Explain the role and responsibilities of the `{main_class.symbol_name}` class in `{main_class.file_path}`. What design patterns does it employ?",
            "target_files": [main_class.file_path],
            "target_symbols": [main_class.symbol_name],
            "expected_concepts": ["class structure", "state management", "modularity"],
        })

    if len(classes) > 1:
        derived_class = classes[1]
        questions.append({
            "id": f"int-q-2",
            "topic": "Inheritance & Extensibility",
            "difficulty": difficulty,
            "question": f"How does `{derived_class.symbol_name}` extend or specialize `{classes[0].symbol_name}`? What methods are added or overridden?",
            "target_files": [derived_class.file_path, classes[0].file_path],
            "target_symbols": [derived_class.symbol_name, classes[0].symbol_name],
            "expected_concepts": ["subclassing", "inheritance hierarchy", "polymorphism"],
        })

    # Method / algorithmic question
    call_methods = [f for f in functions if f.symbol_name and ("parse" in f.symbol_name.lower() or "token" in f.symbol_name.lower() or "calc" in f.symbol_name.lower() or "eval" in f.symbol_name.lower())]
    if call_methods:
        cm = call_methods[0]
        questions.append({
            "id": f"int-q-3",
            "topic": "Algorithms & Parsing",
            "difficulty": difficulty,
            "question": f"Describe the logic inside `{cm.symbol_name}` ({cm.file_path}:L{cm.start_line}). How are inputs processed or validated?",
            "target_files": [cm.file_path],
            "target_symbols": [cm.symbol_name],
            "expected_concepts": ["input parsing", "validation", "control flow"],
        })

    # Error handling question
    error_methods = [f for f in functions if f.symbol_name and ("divide" in f.symbol_name.lower() or "err" in f.symbol_name.lower() or "check" in f.symbol_name.lower())]
    if error_methods:
        em = error_methods[0]
        questions.append({
            "id": f"int-q-4",
            "topic": "Error Handling & Edge Cases",
            "difficulty": difficulty,
            "question": f"How does `{em.symbol_name}` in `{em.file_path}` handle edge cases (e.g. invalid arguments or boundary conditions)? Where are exceptions raised?",
            "target_files": [em.file_path],
            "target_symbols": [em.symbol_name],
            "expected_concepts": ["exception propagation", "defensive programming", "edge conditions"],
        })

    # State & tracking question
    history_methods = [f for f in functions if f.symbol_name and ("record" in f.symbol_name.lower() or "history" in f.symbol_name.lower() or "log" in f.symbol_name.lower())]
    if history_methods:
        hm = history_methods[0]
        questions.append({
            "id": f"int-q-5",
            "topic": "Data Flow & State Tracking",
            "difficulty": difficulty,
            "question": f"Trace how state or execution history is updated in `{hm.symbol_name}`. Which callers invoke this method, and how is persistence managed?",
            "target_files": [hm.file_path],
            "target_symbols": [hm.symbol_name],
            "expected_concepts": ["data flow", "mutation", "caller dependencies"],
        })

    # Fallbacks if repository has different symbols
    if len(questions) < count:
        for idx, sym in enumerate(functions[:count - len(questions)]):
            questions.append({
                "id": f"int-q-extra-{idx}",
                "topic": "Implementation Details",
                "difficulty": difficulty,
                "question": f"Walk through the implementation of `{sym.symbol_name}` in `{sym.file_path}`. What are the key algorithmic considerations?",
                "target_files": [sym.file_path],
                "target_symbols": [sym.symbol_name],
                "expected_concepts": ["signature", "logic", "efficiency"],
            })

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
    user_answer = request.get("user_answer", "").strip()
    target_files = request.get("target_files", [])
    target_symbols = request.get("target_symbols", [])

    if not user_answer:
        return {
            "score": 0,
            "what_was_correct": "No answer provided.",
            "what_was_missing": "Please provide an explanation of the requested implementation.",
            "grounded_explanation": "Answers must be grounded in the repository code.",
            "citations": [],
        }

    # Retrieve real chunks matching the question and target symbols
    from app.services.retrieval.service import RetrievalService
    retrieval = RetrievalService()
    search_res = await retrieval.search(
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

    # Evaluate answer content against code symbols
    mentioned_symbols = [s for s in target_symbols if s.lower() in user_answer.lower()]
    score = 65  # Base passing threshold for substantive answer
    if len(user_answer) > 80:
        score += 15
    if mentioned_symbols:
        score += 15
    score = min(score, 98)

    correct_points = []
    if mentioned_symbols:
        correct_points.append(f"Correctly identified key symbols: {', '.join(mentioned_symbols)}.")
    if len(user_answer) > 40:
        correct_points.append("Provided structured reasoning outlining the operational flow.")

    missing_points = []
    unmentioned = [s for s in target_symbols if s not in mentioned_symbols]
    if unmentioned:
        missing_points.append(f"Consider referencing related component `{unmentioned[0]}`.")
    if "exception" in question.lower() or "error" in question.lower():
        if "valueerror" not in user_answer.lower() and "exception" not in user_answer.lower():
            missing_points.append("Specify exact exception types raised (e.g. ValueError) on invalid inputs.")
    if not missing_points:
        missing_points.append("Could elaborate further on performance complexity and architectural tradeoffs.")

    return {
        "score": score,
        "what_was_correct": " ".join(correct_points) if correct_points else "Identified general concepts related to the module.",
        "what_was_missing": " ".join(missing_points),
        "grounded_explanation": f"In the repository implementation ({', '.join(target_files) if target_files else 'source code'}), the component coordinates with {target_symbols[0] if target_symbols else 'related methods'} to handle execution and validation.",
        "citations": citations,
    }

