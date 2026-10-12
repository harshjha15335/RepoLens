FROM python:3.12-slim

WORKDIR /app/backend
ENV EMBEDDING_PROVIDER=local

# Set to true only for deployments that use transformer embeddings or reranking.
ARG INSTALL_TRANSFORMERS=false

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md ./

# The local embedding provider needs FAISS and the regular API dependencies,
# but neither PyTorch nor sentence-transformers. Keep the package metadata's
# full dependency list for local development and omit only this optional model
# stack in the deployment image.
RUN python -c "import pathlib, subprocess, sys, tomllib; deps = tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['dependencies']; slim = [dep for dep in deps if not dep.startswith('sentence-transformers')]; subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *slim], check=True)"
RUN if [ "$INSTALL_TRANSFORMERS" = "true" ]; then \
      pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
      pip install --no-cache-dir 'sentence-transformers>=2.2.0'; \
    fi

# Copy application
COPY backend/app/ app/
COPY evaluation/datasets/default.json /app/evaluation/datasets/default.json

# Install the application without pulling the model stack back in.
RUN pip install --no-cache-dir --no-deps .

# Create data directory
RUN mkdir -p /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health').raise_for_status()" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
