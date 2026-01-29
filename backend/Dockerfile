# Use Python slim for better compatibility and faster builds
FROM python:3.9-slim-bullseye

WORKDIR /app

# Install only necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py auth_utils.py database.py email_utils.py permissions.py \
     scheduler.py schemas.py supabase_client.py tier_limits.py \
     models.py db_interface.py analytics_processor.py \
     agent_logic.py add_auto_shop.py \
     update_db.py create_sample_data.py ./
COPY routers ./routers/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
