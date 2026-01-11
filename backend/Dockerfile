# Use Python slim for better compatibility and faster builds
FROM python:3.9-slim-bullseye

WORKDIR /app

# Install only necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (no dev packages)
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.23.2 \
    supabase==2.16.0 \
    pydantic==2.4.2 \
    python-jose==3.3.0 \
    passlib==1.7.4 \
    python-multipart==0.0.6 \
    httpx[http2]==0.28.1 \
    python-dotenv==1.0.0 \
    bcrypt==4.0.1 \
    email-validator==2.1.0.post1 \
    sqlalchemy==2.0.36 \
    psycopg2-binary==2.9.10

# Copy only the application code (no tests, dev files)
COPY main.py auth_utils.py database.py email_utils.py permissions.py \
     scheduler.py schemas.py supabase_client.py tier_limits.py ./
COPY routers ./routers/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
