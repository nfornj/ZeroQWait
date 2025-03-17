FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install -U pip setuptools wheel
RUN pip install pdm==2.10.0

# Set environment variables
ENV PDM_USE_VENV=false
ENV PDM_IGNORE_SAVED_PYTHON=1
ENV PYTHONPATH=/app/__pypackages__/3.9/lib
ENV PATH="/app/__pypackages__/3.9/bin:$PATH"

# Copy project files first
COPY pyproject.toml pdm.toml README.md ./

# Initialize PDM and install dependencies
RUN pdm install --no-lock --no-editable

# Copy the rest of the application code
COPY . .

# Run the application
CMD ["pdm", "run", "start"] 