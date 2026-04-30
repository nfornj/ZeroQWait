FROM python:3.11-slim

# System deps required by piper-tts (espeak-ng for phonemization, libgomp for ONNX runtime)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libespeak-ng1 libgomp1 wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install piper-tts and API server deps
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Download Piper ONNX voice models at build time so the image is self-contained
RUN mkdir -p /app/models

ARG PIPER_BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US

RUN wget -q "${PIPER_BASE}/lessac/medium/en_US-lessac-medium.onnx" \
        -O /app/models/en_US-lessac-medium.onnx && \
    wget -q "${PIPER_BASE}/lessac/medium/en_US-lessac-medium.onnx.json" \
        -O /app/models/en_US-lessac-medium.onnx.json && \
    wget -q "${PIPER_BASE}/ryan/medium/en_US-ryan-medium.onnx" \
        -O /app/models/en_US-ryan-medium.onnx && \
    wget -q "${PIPER_BASE}/ryan/medium/en_US-ryan-medium.onnx.json" \
        -O /app/models/en_US-ryan-medium.onnx.json

COPY main.py /app/main.py
WORKDIR /app

ENV MODELS_DIR=/app/models
ENV TTS_DEFAULT_VOICE=female

EXPOSE 8880

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8880"]
