FROM python:3.11-slim

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY mcps/postgres/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY mcps/postgres ./mcps/postgres

USER appuser

ENV HOST=0.0.0.0
ENV PORT=8894

EXPOSE 8894

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx, sys; r=httpx.get('http://localhost:8894/health', timeout=5); sys.exit(0 if r.status_code==200 else 1)"

CMD ["python", "mcps/postgres/server.py"]
