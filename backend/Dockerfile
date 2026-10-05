FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi uvicorn pydantic pydantic-settings \
    "sqlalchemy[asyncio]" aiosqlite python-multipart \
    httpx numpy faiss-cpu sentence-transformers \
    "tree-sitter>=0.22.0" tree-sitter-python tree-sitter-javascript \
    tree-sitter-typescript tree-sitter-java tree-sitter-c \
    tree-sitter-cpp tree-sitter-go

# Copy application
COPY app/ app/

# Create data directory
RUN mkdir -p /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
