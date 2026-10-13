"""SQLAlchemy database models for CodeMentor-RAG."""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RepositoryStatus(str, PyEnum):
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


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # "zip", "git", "local"
    source_url = Column(String, nullable=True)
    status = Column(
        Enum(RepositoryStatus), default=RepositoryStatus.PENDING, nullable=False
    )
    progress = Column(Integer, default=0)
    progress_message = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    storage_path = Column(String, nullable=True)

    # Stats
    file_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    symbol_count = Column(Integer, default=0)
    graph_node_count = Column(Integer, default=0)
    graph_edge_count = Column(Integer, default=0)
    languages = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    indexed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    files = relationship("RepositoryFile", back_populates="repository", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="repository", cascade="all, delete-orphan")
    sessions = relationship("ChatSession", back_populates="repository", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_repositories_status", "status"),
    )


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id = Column(String, primary_key=True, default=generate_uuid)
    repository_id = Column(String, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    path = Column(String, nullable=False)
    language = Column(String, nullable=True)
    size_bytes = Column(Integer, default=0)
    content_hash = Column(String, nullable=True)
    is_parsed = Column(Boolean, default=False)
    symbol_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    repository = relationship("Repository", back_populates="files")
    chunks = relationship("Chunk", back_populates="file", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_repository_files_repo_id", "repository_id"),
        Index("ix_repository_files_path", "repository_id", "path"),
    )


class RepositoryArtifact(Base):
    """Durable copy of files needed when a service instance loses its local disk."""
    __tablename__ = "repository_artifacts"

    repository_id = Column(String, ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True)
    kind = Column(String, primary_key=True)
    payload = Column(LargeBinary, nullable=False)
    revision = Column(String, default=generate_uuid, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    repository_id = Column(String, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(String, ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, default=0)

    # Content
    content = Column(Text, nullable=False)
    content_hash = Column(String, nullable=True)

    # Metadata
    file_path = Column(String, nullable=False)
    language = Column(String, nullable=True)
    symbol_name = Column(String, nullable=True)
    symbol_type = Column(String, nullable=True)  # file, class, function, method, etc.
    parent_symbol = Column(String, nullable=True)
    start_line = Column(Integer, nullable=True)
    end_line = Column(Integer, nullable=True)
    imports = Column(JSON, default=list)
    definitions = Column(JSON, default=list)

    # Embedding index position (for FAISS ID mapping)
    faiss_index = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    repository = relationship("Repository", back_populates="chunks")
    file = relationship("RepositoryFile", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_repo_id", "repository_id"),
        Index("ix_chunks_file_id", "file_id"),
        Index("ix_chunks_symbol", "repository_id", "symbol_name"),
        Index("ix_chunks_content_hash", "content_hash"),
    )


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True, default=generate_uuid)
    repository_id = Column(String, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    node_type = Column(String, nullable=False)  # file, class, function, method
    name = Column(String, nullable=False)
    qualified_name = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    start_line = Column(Integer, nullable=True)
    end_line = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_graph_nodes_repo_id", "repository_id"),
        Index("ix_graph_nodes_name", "repository_id", "name"),
        Index("ix_graph_nodes_qualified", "repository_id", "qualified_name"),
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True, default=generate_uuid)
    repository_id = Column(String, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String, nullable=False)  # CONTAINS, IMPORTS, CALLS, INHERITS
    metadata_ = Column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_graph_edges_repo_id", "repository_id"),
        Index("ix_graph_edges_source", "source_id"),
        Index("ix_graph_edges_target", "target_id"),
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    repository_id = Column(String, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=True)
    tutor_mode = Column(String, default="developer")  # beginner, developer, interview, debug
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    repository = relationship("Repository", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan",
                          order_by="ChatMessage.created_at")

    __table_args__ = (
        Index("ix_chat_sessions_repo_id", "repository_id"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    citations = Column(JSON, default=list)
    retrieval_metadata = Column(JSON, default=dict)  # strategy info, latencies, etc.
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("ix_chat_messages_session_id", "session_id"),
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    repository_id = Column(String, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    strategy = Column(String, nullable=False)
    config = Column(JSON, default=dict)
    status = Column(String, default="running")  # running, completed, failed

    # Metrics
    recall_at_5 = Column(Float, nullable=True)
    recall_at_10 = Column(Float, nullable=True)
    mrr = Column(Float, nullable=True)
    avg_retrieval_latency_ms = Column(Float, nullable=True)
    avg_generation_latency_ms = Column(Float, nullable=True)

    results = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_evaluation_runs_repo_id", "repository_id"),
    )
