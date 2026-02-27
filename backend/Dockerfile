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

# Install Python dependencies using uv
COPY pyproject.toml uv.lock .python-version ./
# Sync dependencies to create a pristine virtual environment
RUN uv sync --no-dev

# Copy the application code
COPY . .

# Pre-warm the sentence-transformer model so first requests don't block on download
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# Expose port
EXPOSE 8000

# Run the application using the uv environment
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
