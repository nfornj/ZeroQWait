"""
Qwen3-TTS OpenAI-compatible API wrapper.

Exposes POST /v1/audio/speech compatible with the OpenAI TTS API,
backed by Qwen3-TTS-12Hz-0.6B-CustomVoice.
"""

import asyncio
import io
import os
import logging

import torch
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qwen3-tts-service")

app = FastAPI(title="Qwen3-TTS Service")

MODEL_NAME = os.getenv("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")

# Global model reference and generation lock (GPU is single-threaded)
_model = None
_gen_lock = asyncio.Lock()

# Qwen3-TTS built-in speakers for CustomVoice models
VALID_SPEAKERS = {
    "Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric",
    "Ryan", "Aiden", "Ono_Anna", "Sohee",
}

# Map common/OpenAI voice names to Qwen3-TTS speakers
VOICE_MAP = {
    "serena": "Serena",
    "vivian": "Vivian",
    "ryan": "Ryan",
    "aiden": "Aiden",
    "eric": "Eric",
    "dylan": "Dylan",
    "uncle_fu": "Uncle_Fu",
    "ono_anna": "Ono_Anna",
    "sohee": "Sohee",
    # OpenAI-compatible aliases
    "alloy": "Serena",
    "nova": "Vivian",
    "echo": "Ryan",
    "onyx": "Aiden",
    "fable": "Serena",
    "shimmer": "Vivian",
    # Legacy Kokoro aliases
    "af_heart": "Serena",
}


class SpeechRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str = "Serena"
    speed: float = 1.0
    response_format: str = "wav"


def _resolve_speaker(voice: str) -> str:
    """Resolve voice name to a valid Qwen3-TTS speaker."""
    # Try direct match (case-sensitive)
    if voice in VALID_SPEAKERS:
        return voice
    # Try case-insensitive lookup
    mapped = VOICE_MAP.get(voice.lower())
    if mapped:
        return mapped
    # Default fallback
    logger.warning(f"Unknown voice '{voice}', falling back to Serena")
    return "Serena"


@app.on_event("startup")
async def load_model():
    global _model
    from qwen_tts import Qwen3TTSModel

    logger.info(f"Loading Qwen3-TTS model: {MODEL_NAME}")
    _model = Qwen3TTSModel.from_pretrained(
        MODEL_NAME,
        device_map="cuda:0",
        dtype=torch.bfloat16,
    )
    logger.info("Qwen3-TTS model loaded successfully")


@app.get("/health")
async def health():
    return {"status": "healthy" if _model is not None else "loading"}


@app.post("/v1/audio/speech")
async def create_speech(req: SpeechRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    text = (req.input or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Input text is empty")

    speaker = _resolve_speaker(req.voice)

    async with _gen_lock:
        try:
            wavs, sr = await asyncio.to_thread(
                _model.generate_custom_voice,
                text=text,
                language="Auto",
                speaker=speaker,
            )
        except Exception as e:
            logger.error(f"TTS generation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    buf = io.BytesIO()
    sf.write(buf, wavs[0], sr, format="WAV")
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=speech.wav"},
    )
