"""Pydantic request/response schemas for CodeMentor-RAG API."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# ─── Enums ───────────────────────────────────────────────────────

class RepositoryStatusEnum(str, Enum):
    PENDING = "PENDING"
    DISCOVERING = "DISCOVERING"
    PARSING = "PARSING"
    CHUNKING = "CHUNKING"
    BUILDING_GRAPH = "BUILDING_GRAPH"
    EMBEDDING = "EMBEDDING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TutorMode(str, Enum):
    BEGINNER = "beginner"
    DEVELOPER = "developer"
    INTERVIEW = "interview"
    DEBUG = "debug"


class QueryIntent(str, Enum):
    REPOSITORY_OVERVIEW = "REPOSITORY_OVERVIEW"
    SYMBOL_LOOKUP = "SYMBOL_LOOKUP"
    IMPLEMENTATION_EXPLANATION = "IMPLEMENTATION_EXPLANATION"
    ARCHITECTURE = "ARCHITECTURE"
    DEPENDENCY = "DEPENDENCY"
    CALL_FLOW = "CALL_FLOW"
    DEBUGGING = "DEBUGGING"
    DOCUMENTATION = "DOCUMENTATION"
    GENERAL_CODE_QUESTION = "GENERAL_CODE_QUESTION"


# ─── Repository Schemas ─────────────────────────────────────────

class RepositoryStats(BaseModel):
    files: int = 0
    chunks: int = 0
    symbols: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0


class RepositoryResponse(BaseModel):
    id: str
    name: str
    source_type: str
    status: RepositoryStatusEnum
    progress: int = 0
    progress_message: str | None = None
    error_message: str | None = None
    languages: list[str] = []
    stats: RepositoryStats = RepositoryStats()
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RepositoryListResponse(BaseModel):
    repositories: list[RepositoryResponse]
    total: int


class GitImportRequest(BaseModel):
    url: str = Field(..., description="Git repository URL")
    branch: str | None = Field(None, description="Branch to clone")


# ─── File Schemas ─────────────────────────────────────────────────

class FileInfo(BaseModel):
    id: str
    path: str
    language: str | None = None
    size_bytes: int = 0
    symbol_count: int = 0
    chunk_count: int = 0

    model_config = {"from_attributes": True}


class FileTreeNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    children: list["FileTreeNode"] = []
    language: str | None = None
    size_bytes: int = 0


class FileContentResponse(BaseModel):
    path: str
    content: str
    language: str | None = None
    total_lines: int = 0


class UpdateFileContentRequest(BaseModel):
    path: str = Field(..., description="File path within the repository")
    content: str = Field(..., description="Updated file content")


# ─── Symbol Schemas ───────────────────────────────────────────────

class SymbolInfo(BaseModel):
    name: str
    symbol_type: str
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    parent_symbol: str | None = None


class SymbolListResponse(BaseModel):
    symbols: list[SymbolInfo]
    total: int


# ─── Chat Schemas ─────────────────────────────────────────────────

class Citation(BaseModel):
    chunk_id: str | None = None
    file_path: str
    symbol: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    content_preview: str | None = None


class CodeContext(BaseModel):
    action: Literal["explain", "debug", "trace"] | None = None
    file_path: str = Field(..., min_length=1)
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    text: str | None = None


class ChatRequest(BaseModel):
    repository_id: str
    session_id: str | None = None
    question: str = Field(..., min_length=1, max_length=2000)
    tutor_mode: TutorMode = TutorMode.DEVELOPER
    stream: Literal[False] = False
    code_context: CodeContext | None = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    citations: list[Citation] = []
    retrieval_metadata: dict = {}


class SessionResponse(BaseModel):
    id: str
    repository_id: str
    title: str | None = None
    tutor_mode: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: list[Citation] = []
    retrieval_metadata: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDetailResponse(BaseModel):
    id: str
    repository_id: str
    title: str | None = None
    tutor_mode: str
    messages: list[MessageResponse] = []
    created_at: datetime


# ─── Retrieval Schemas ────────────────────────────────────────────

class RetrievalRequest(BaseModel):
    repository_id: str
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    strategy: str = "hybrid"  # dense, bm25, hybrid
    enable_graph_expansion: bool = True
    enable_mmr: bool = True
    enable_reranking: bool = False


class RetrievedChunk(BaseModel):
    chunk_id: str
    file_path: str
    symbol_name: str | None = None
    symbol_type: str | None = None
    content: str
    start_line: int | None = None
    end_line: int | None = None
    score: float = 0.0
    rank: int = 0
    source: str = ""  # dense, bm25, rrf, graph, reranker


class RetrievalResponse(BaseModel):
    query: str
    intent: str | None = None
    chunks: list[RetrievedChunk] = []
    total_retrieved: int = 0
    latency_ms: float = 0.0
    strategy: str = ""


# ─── Evaluation Schemas ──────────────────────────────────────────

class EvaluationRequest(BaseModel):
    repository_id: str
    dataset_path: str | None = None
    strategies: list[str] = ["dense", "bm25", "hybrid"]


class EvaluationMetrics(BaseModel):
    strategy: str
    recall_at_5: float | None = None
    recall_at_10: float | None = None
    mrr: float | None = None
    avg_latency_ms: float | None = None
    results: list[dict] = []


class EvaluationResponse(BaseModel):
    id: str
    repository_id: str
    status: str
    metrics: list[EvaluationMetrics] = []
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


# ─── Health Schema ────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    components: dict = {}


# ─── Error Schema ─────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    request_id: str | None = None
