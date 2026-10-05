"""Custom exception classes for CodeMentor-RAG."""


class CodeMentorError(Exception):
    """Base exception for CodeMentor-RAG."""

    def __init__(self, message: str, detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class RepositoryValidationError(CodeMentorError):
    """Error during repository validation."""
    pass


class ArchiveSecurityError(CodeMentorError):
    """Security violation detected in archive."""
    pass


class ParserError(CodeMentorError):
    """Error during code parsing."""
    pass


class EmbeddingProviderError(CodeMentorError):
    """Error from the embedding provider."""
    pass


class IndexError_(CodeMentorError):
    """Error during index operations."""
    pass


class RetrievalError(CodeMentorError):
    """Error during retrieval."""
    pass


class GenerationProviderError(CodeMentorError):
    """Error from the generation provider."""
    pass


class EvaluationError(CodeMentorError):
    """Error during evaluation."""
    pass


class RepositoryNotFoundError(CodeMentorError):
    """Repository not found."""
    pass


class SessionNotFoundError(CodeMentorError):
    """Chat session not found."""
    pass


class IngestionInProgressError(CodeMentorError):
    """Ingestion is already in progress."""
    pass
