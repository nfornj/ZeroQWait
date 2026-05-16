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


def _get_synthesizer():
    global _synthesizer
    if _synthesizer is None:
        with _synth_lock:
            if _synthesizer is None:
                logger.info("Loading Qwen3-TTS model: %s", MODEL_NAME)
                try:
                    # qwen-tts >= 0.1 API
                    from qwen_tts import SpeechSynthesizer  # type: ignore[import]
                    _synthesizer = SpeechSynthesizer(
                        model=MODEL_NAME,
                        voice=DEFAULT_VOICE,
                    )
                    logger.info("Qwen3-TTS model loaded successfully with voice '%s'", DEFAULT_VOICE)
                except ImportError:
                    # Fallback: use transformers pipeline
                    import torch
                    from transformers import pipeline  # type: ignore[import]
                    device = 0 if torch.cuda.is_available() else -1
                    logger.info("qwen_tts not found, using transformers pipeline on device=%d", device)
                    _synthesizer = pipeline("text-to-speech", model=MODEL_NAME, device=device)
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


def _synthesize_sync(text: str, voice: str, speed: float, language: str, instruct: Optional[str]) -> bytes:
    """Blocking synthesis; called via run_in_executor."""
    synth = _get_synthesizer()

    # qwen-tts SpeechSynthesizer path
    if hasattr(synth, "call"):
        audio_data = synth.call(text)
        if isinstance(audio_data, bytes):
            return audio_data
        # If numpy array returned, convert to WAV
        return _pcm_to_wav(np.array(audio_data), 24000)

    # transformers pipeline path
    result = synth(text)
    audio_array = result["audio"]
    sampling_rate = result.get("sampling_rate", 24000)
    return _pcm_to_wav(np.array(audio_array).flatten(), sampling_rate)


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
            req.speed,
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
    """Return 'female' or 'male'; unknown values default to female."""
    lower = voice_name.strip().lower()
    if lower in VOICE_MODELS:
        return lower
    logger.warning("Unknown voice '%s', defaulting to female", voice_name)
    return "female"


# ---------------------------------------------------------------------------
# Synthesis helper — runs in a thread pool (piper is synchronous)
# ---------------------------------------------------------------------------
def _synthesize_sync(text: str, gender: str, length_scale: float) -> bytes:
    """Blocking synthesis; called via run_in_executor from async handlers.

    piper-tts >= 1.4 API: synthesize() returns Iterable[AudioChunk] with
    audio_int16_bytes (raw 16-bit PCM mono). We wrap the chunks into a WAV
    container here instead of passing a wave.Wave_write to piper.
    """
    from piper.config import SynthesisConfig  # type: ignore[import]

    voice = _get_voice(gender)
    syn_cfg = SynthesisConfig(length_scale=length_scale)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)       # mono
        wf.setsampwidth(2)       # 16-bit PCM
        wf.setframerate(voice.config.sample_rate)
        for chunk in voice.synthesize(text, syn_config=syn_cfg):
            wf.writeframes(chunk.audio_int16_bytes)
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
    input: str
    voice: str = DEFAULT_VOICE
    speed: float = 1.0


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
