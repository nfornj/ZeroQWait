FROM python:3.11-slim

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY mcps/finance/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY mcps/finance ./mcps/finance

USER appuser

ENV HOST=0.0.0.0
ENV PORT=8891

EXPOSE 8891

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx, sys; r=httpx.get('http://localhost:8891/health', timeout=5); sys.exit(0 if r.status_code==200 else 1)"

CMD ["python", "mcps/finance/server.py"]
