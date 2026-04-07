# Use Python slim for better compatibility and faster builds
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install only necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv dependency manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install venv at /opt/venv so that the bind-mounted volume at /app does NOT
# shadow the virtual environment at container runtime.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies using uv
COPY pyproject.toml uv.lock .python-version ./
# Sync dependencies to create a pristine virtual environment
RUN uv sync --no-dev

# Copy the application code
COPY . .

# Pre-warm the sentence-transformer model so first requests don't block on download
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# Expose port
EXPOSE 8000

# Run uvicorn directly from the venv — no uv runtime overhead, and
# works correctly even when /app is overridden by a bind mount volume.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
