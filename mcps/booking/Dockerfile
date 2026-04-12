FROM python:3.11-slim

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

USER appuser

ENV HOST=0.0.0.0
ENV PORT=8890

EXPOSE 8890

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx, sys; r=httpx.get('http://localhost:8890/health', timeout=5); sys.exit(0 if r.status_code==200 else 1)"

CMD ["python", "server.py"]
