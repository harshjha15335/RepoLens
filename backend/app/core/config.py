"""Core configuration for CodeMentor-RAG backend."""

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Data Storage
    data_dir: str = Field(default="./data", alias="DATA_DIR")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/codementor.db",
        alias="DATABASE_URL",
    )

    # Upload Limits
    max_upload_mb: int = Field(default=500, alias="MAX_UPLOAD_MB")
    max_extracted_mb: int = Field(default=2000, alias="MAX_EXTRACTED_MB")
    max_repository_files: int = Field(default=10000, alias="MAX_REPOSITORY_FILES")
    max_file_mb: int = Field(default=10, alias="MAX_FILE_MB")

    # Embedding Configuration
    embedding_provider: str = Field(
        default="sentence-transformers", alias="EMBEDDING_PROVIDER"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")

    # LLM Configuration
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    llm_model: str = Field(default="llama3.1:8b", alias="LLM_MODEL")
    llm_base_url: str = Field(
        default="http://localhost:11434", alias="LLM_BASE_URL"
    )
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")

    # Reranker Configuration
    reranker_provider: str = Field(default="none", alias="RERANKER_PROVIDER")
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2", alias="RERANKER_MODEL"
    )

    # Retrieval Configuration
    dense_top_k: int = Field(default=20, alias="DENSE_TOP_K")
    bm25_top_k: int = Field(default=20, alias="BM25_TOP_K")
    final_top_k: int = Field(default=10, alias="FINAL_TOP_K")
    rrf_k: int = Field(default=60, alias="RRF_K")
    mmr_enabled: bool = Field(default=True, alias="MMR_ENABLED")
    mmr_lambda: float = Field(default=0.7, alias="MMR_LAMBDA")
    rerank_enabled: bool = Field(default=False, alias="RERANK_ENABLED")

    # Generation Configuration
    context_token_budget: int = Field(default=4096, alias="CONTEXT_TOKEN_BUDGET")
    generation_max_tokens: int = Field(
        default=2048, alias="GENERATION_MAX_TOKENS"
    )

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def data_path(self) -> Path:
        """Get the data directory as a Path object."""
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def repos_path(self) -> Path:
        """Get the repositories storage directory."""
        path = self.data_path / "repositories"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def indexes_path(self) -> Path:
        """Get the indexes storage directory."""
        path = self.data_path / "indexes"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def max_extracted_bytes(self) -> int:
        return self.max_extracted_mb * 1024 * 1024

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
