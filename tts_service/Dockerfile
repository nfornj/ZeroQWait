FROM nvidia/cuda:12.8.0-runtime-ubuntu24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

# Create venv to avoid PEP 668 issues
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install TTS dependencies (includes qwen-tts and all its deps like librosa)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Force-reinstall CUDA-compatible torch + torchaudio AFTER qwen-tts (overrides CPU wheels)
RUN pip install --no-cache-dir --force-reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu128

COPY main.py /app/main.py
WORKDIR /app

# HuggingFace cache directory (mount as volume for persistence)
ENV HF_HOME=/data/huggingface
ENV TRANSFORMERS_CACHE=/data/huggingface

EXPOSE 8880

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8880"]
