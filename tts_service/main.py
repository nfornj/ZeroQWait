"""
Qwen3-TTS service — OpenAI-compatible /v1/audio/speech endpoint.

Voice: Vivian (warm, clear North American English accent)
Model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
GPU: CUDA (RTX 5060 Ti, sm_89)

POST /v1/audio/speech
GET  /health
"""

import asyncio
import io
import logging
import os
import threading
import wave
from typing import Optional

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qwen3-tts-service")

app = FastAPI(title="Qwen3-TTS Service", version="1.0.0")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
DEFAULT_VOICE = os.getenv("TTS_DEFAULT_VOICE", "Vivian")
HF_HOME = os.getenv("HF_HOME", "/data/huggingface")

# ---------------------------------------------------------------------------
# Model loader — lazy-load, thread-safe
# ---------------------------------------------------------------------------
_synthesizer = None
_synth_lock = threading.Lock()
_sample_rate = 24000


def _get_synthesizer():
    global _synthesizer
    if _synthesizer is None:
        with _synth_lock:
            if _synthesizer is None:
                logger.info("Loading Qwen3-TTS model: %s", MODEL_NAME)
                from qwen_tts import Qwen3TTSModel  # type: ignore[import]
                device_map = "cuda" if torch.cuda.is_available() else "cpu"
                dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
                logger.info("Using device_map=%s dtype=%s", device_map, dtype)
                _synthesizer = Qwen3TTSModel.from_pretrained(
                    MODEL_NAME,
                    device_map=device_map,
                    dtype=dtype,
                )
                logger.info("Qwen3-TTS model loaded with voice '%s'", DEFAULT_VOICE)
    return _synthesizer


def _pcm_to_wav(pcm_data: np.ndarray, sample_rate: int) -> bytes:
    """Convert float32/int16 numpy array to WAV bytes."""
    buf = io.BytesIO()
    if pcm_data.dtype != np.int16:
        pcm_int16 = (pcm_data * 32767).clip(-32768, 32767).astype(np.int16)
    else:
        pcm_int16 = pcm_data.flatten()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16.tobytes())
    return buf.getvalue()


def _synthesize_sync(text: str, voice: str, language: str, instruct: Optional[str]) -> bytes:
    """Blocking synthesis; called via run_in_executor."""
    model = _get_synthesizer()
    wavs, sr = model.generate_custom_voice(
        text=text,
        speaker=voice,
        language=language,
        instruct=instruct or None,
    )
    return _pcm_to_wav(np.array(wavs[0]).flatten(), sr)


# ---------------------------------------------------------------------------
# Startup: pre-load model
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup():
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _get_synthesizer)
        logger.info("Qwen3-TTS ready — voice: %s", DEFAULT_VOICE)
    except Exception as exc:
        logger.error("Failed to preload Qwen3-TTS model: %s", exc)


# ---------------------------------------------------------------------------
# Request schema — OpenAI-compatible
# ---------------------------------------------------------------------------
class TTSRequest(BaseModel):
    model: str = "tts-1-en"
    input: Optional[str] = None
    text: Optional[str] = None       # alias used by some clients
    voice: str = "Vivian"
    speed: float = 1.0
    response_format: str = "wav"
    language: str = "English"
    instruct: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/v1/audio/speech")
async def speech(req: TTSRequest):
    text = req.input or req.text or ""
    if not text.strip():
        raise HTTPException(status_code=400, detail="No input text provided")

    voice = req.voice if req.voice else DEFAULT_VOICE
    try:
        loop = asyncio.get_event_loop()
        audio_bytes = await loop.run_in_executor(
            None,
            _synthesize_sync,
            text,
            voice,
            req.language,
            req.instruct,
        )
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"X-Voice": voice},
        )
    except Exception as exc:
        logger.error("TTS synthesis failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"TTS synthesis error: {exc}")


@app.get("/health")
async def health():
    """Readiness probe — returns 200 once model is loaded."""
    synth = _synthesizer
    if synth is None:
        # Model not yet loaded — let startup probe handle this
        raise HTTPException(status_code=503, detail="Model loading")
    return {"status": "ok", "model": MODEL_NAME, "voice": DEFAULT_VOICE}
