# Use Python slim for better compatibility and faster builds
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install only necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv via pip — avoids a COPY --from=ghcr.io/astral-sh/uv which fails
# when the runner's ghcr.io token only covers the project's own namespace.
RUN pip install --no-cache-dir uv

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

# Create a non-root user (UID 1000) and own the venv + app dirs before switching to it.
# This fixes 'getpwuid(): uid not found' from sentence-transformers and satisfies
# the K8s securityContext runAsNonRoot: true / runAsUser: 1000 requirement.
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app /opt/venv
USER appuser
ENV HOME=/home/appuser

# Pre-warm the sentence-transformer model as appuser so the HuggingFace cache
# lands in /home/appuser/.cache and is readable at runtime under UID 1000.
ARG PREWARM_SENTENCE_TRANSFORMER=1
RUN if [ "$PREWARM_SENTENCE_TRANSFORMER" = "1" ]; then \
        python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true; \
    else \
        echo "Skipping sentence-transformer prewarm"; \
    fi

# Expose port
EXPOSE 8000

# Run uvicorn directly from the venv — no uv runtime overhead.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
