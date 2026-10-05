"""Structured logging configuration for CodeMentor-RAG."""

import logging
import sys
import uuid
from contextvars import ContextVar

from app.core.config import get_settings

# Context variable for request correlation
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class CorrelationFilter(logging.Filter):
    """Add request_id to log records."""

    def filter(self, record):
        record.request_id = request_id_var.get("")
        return True


def setup_logging():
    """Configure structured logging."""
    settings = get_settings()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


def generate_request_id() -> str:
    """Generate a new request correlation ID."""
    return str(uuid.uuid4())[:8]
