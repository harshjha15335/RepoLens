FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install the CPU-only PyTorch wheel before the project dependencies so
# sentence-transformers does not pull the default CUDA-enabled distribution.
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

# Copy application
COPY app/ app/

# Install dependencies declared by the project without an editable install.
RUN pip install --no-cache-dir .

# Create data directory
RUN mkdir -p /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health').raise_for_status()" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
