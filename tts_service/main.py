"""
Piper TTS — OpenAI-compatible API wrapper.

Exposes POST /v1/audio/speech compatible with the OpenAI TTS API,
backed by CPU-only Piper ONNX voice models.

Voices
------
  female  — en_US-lessac-medium  (default, warm clear North American English)
  male    — en_US-ryan-medium    (clear North American English male)

All legacy Qwen3-TTS/OpenAI voice aliases are accepted and mapped to
the appropriate gender automatically.
"""

import asyncio
import io
import logging
import os
import threading
import wave
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("piper-tts-service")

app = FastAPI(title="Piper TTS Service", version="1.0.0")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODELS_DIR = os.getenv("MODELS_DIR", "/app/models")
DEFAULT_VOICE = os.getenv("TTS_DEFAULT_VOICE", "female")

# Voice model file names (ONNX files baked into the Docker image)
VOICE_MODELS: Dict[str, str] = {
    "female": "en_US-lessac-medium.onnx",
    "male":   "en_US-ryan-medium.onnx",
}

# Aliases -> canonical gender key
VOICE_ALIASES: Dict[str, str] = {
    # female aliases (legacy Qwen3-TTS + OpenAI compat)
    "vivian":   "female",
    "serena":   "female",
    "nova":     "female",
    "shimmer":  "female",
    "alloy":    "female",
    "fable":    "female",
    "af_heart": "female",
    "ono_anna": "female",
    "sohee":    "female",
    # male aliases
    "ryan":     "male",
    "echo":     "male",
    "onyx":     "male",
    "aiden":    "male",
    "dylan":    "male",
    "eric":     "male",
    "uncle_fu": "male",
}

# ---------------------------------------------------------------------------
# Voice loader — lazy-load, thread-safe, one instance per gender
# ---------------------------------------------------------------------------
_voices: Dict[str, object] = {}
_voice_lock = threading.Lock()


def _load_voice(gender: str):
    from piper import PiperVoice  # type: ignore[import]
    model_path = os.path.join(MODELS_DIR, VOICE_MODELS[gender])
    logger.info("Loading Piper voice '%s' from %s", gender, model_path)
    return PiperVoice.load(model_path)


def _get_voice(gender: str):
    with _voice_lock:
        if gender not in _voices:
            _voices[gender] = _load_voice(gender)
    return _voices[gender]


def _resolve_voice(voice_name: str) -> str:
    """Return 'female' or 'male' from any voice name string."""
    lower = voice_name.strip().lower()
    if lower in VOICE_MODELS:
        return lower
    resolved = VOICE_ALIASES.get(lower)
    if resolved:
        return resolved
    logger.warning("Unknown voice '%s', defaulting to female", voice_name)
    return "female"


# ---------------------------------------------------------------------------
# Synthesis helper — runs in a thread pool (piper is synchronous)
# ---------------------------------------------------------------------------
def _synthesize_sync(text: str, gender: str, length_scale: float) -> bytes:
    """Blocking synthesis; called via run_in_executor from async handlers."""
    voice = _get_voice(gender)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        voice.synthesize(text, wf, length_scale=length_scale)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Startup: pre-load both voices so the first request is fast
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup():
    loop = asyncio.get_event_loop()
    for gender in VOICE_MODELS:
        try:
            await loop.run_in_executor(None, _get_voice, gender)
            logger.info("Piper voice '%s' ready", gender)
        except Exception as exc:
            logger.error("Failed to preload voice '%s': %s", gender, exc, exc_info=True)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
class SpeechRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str = DEFAULT_VOICE
    speed: float = 1.0
    response_format: str = "wav"
    # Accepted but ignored — kept for API compat with old Qwen3-TTS callers
    language: str = "English"
    instruct: str = ""


@app.post("/v1/audio/speech")
async def synthesize_speech(req: SpeechRequest):
    text = req.input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="input text is required")

    gender = _resolve_voice(req.voice)
    # Piper uses length_scale (inverse of speed): speed=2.0 => 0.5x duration
    length_scale = max(0.1, 1.0 / max(req.speed, 0.1))

    try:
        loop = asyncio.get_event_loop()
        audio_bytes = await loop.run_in_executor(
            None, _synthesize_sync, text, gender, length_scale
        )
    except Exception as exc:
        logger.error("Piper synthesis error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {exc}")

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "X-Piper-Voice": gender,
            "X-Piper-Model": VOICE_MODELS[gender],
        },
    )


@app.get("/health")
async def health():
    loaded = [g for g in VOICE_MODELS if g in _voices]
    return {
        "status": "ok",
        "engine": "piper",
        "voices": {
            "available": list(VOICE_MODELS.keys()),
            "loaded": loaded,
            "default": DEFAULT_VOICE,
        },
    }
