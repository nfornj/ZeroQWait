import httpx
import os
import hashlib
import time
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)
router = APIRouter()

ASR_SERVICE_URL = os.getenv("ASR_SERVICE_URL", "http://asr-service.zeroqwait.svc.cluster.local:8000/transcribe")
# TTS service - running on the host machine port 8880
TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", "http://192.168.2.88:8880")
# TTS Redis cache TTL: default 24 h, override via TTS_CACHE_TTL_SECONDS env var
TTS_CACHE_TTL = int(os.getenv("TTS_CACHE_TTL_SECONDS", "86400"))

# L1 in-process fallback cache (used when Redis is unavailable)
_tts_l1_cache: Dict[str, Tuple[bytes, str, str]] = {}
_TTS_L1_MAX_ITEMS = 128


def _tts_cache_key(text: str, voice: str, speed: float) -> str:
    return hashlib.sha256(
        f"{text}|{voice}|{speed}".encode("utf-8")
    ).hexdigest()


def detect_audio_format(audio_bytes: bytes) -> tuple[str, str]:
    """Detect audio format from magic bytes and return (format, mime_type)."""
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return "wav", "audio/wav"
    if len(audio_bytes) >= 3 and audio_bytes[:3] == b"ID3":
        return "mp3", "audio/mpeg"
    if len(audio_bytes) >= 2 and audio_bytes[:2] == b"\xff\xfb":
        return "mp3", "audio/mpeg"
    return "unknown", "application/octet-stream"


class TTSRequest(BaseModel):
    text: str
    voice: str = "Vivian"
    speed: float = 1.0

@router.post("/transcribe")
async def transcribe_voice(file: UploadFile = File(...)):
    """
    Receives an audio file from the frontend, forwards it to the GPU-accelerated 
    ASR service, and returns the transcribed text.
    """
    try:
        file_content = await file.read()
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {'file': (file.filename, file_content, file.content_type)}
            response = await client.post(ASR_SERVICE_URL, files=files)
            if response.status_code != 200:
                logger.error(f"ASR Service Failed: {response.text}")
                raise HTTPException(status_code=502, detail="ASR Service unavailable")
            return response.json()
    except Exception as e:
        logger.error(f"Voice Transcription Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    """
    Proxy TTS request to the TTS service.
    Checks Redis TTS cache first (cross-pod, 24 h TTL), then falls back to
    an in-process L1 dict, then synthesises via the Qwen3-TTS service.
    Returns buffered WAV audio for the frontend to play.
    """
    from redis_client import redis_client

    cache_key = _tts_cache_key(req.text, req.voice, req.speed)
    t0 = time.perf_counter()

    # L2: Redis cache (shared across all backend pods)
    cached_bytes = redis_client.get_tts_cache(cache_key)
    if cached_bytes is not None:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        redis_client.record_tts_hit(latency_ms)
        audio_format, media_type = detect_audio_format(cached_bytes)
        return Response(
            content=cached_bytes,
            media_type=media_type,
            headers={
                "Cache-Control": "no-cache",
                "X-Audio-Format": audio_format,
                "X-TTS-Cache": "HIT-REDIS",
            },
        )

    # L1: in-process fallback (survives Redis unavailability)
    l1 = _tts_l1_cache.get(cache_key)
    if l1 is not None:
        audio_bytes, media_type, audio_format = l1
        redis_client.record_tts_hit((time.perf_counter() - t0) * 1000.0)
        return Response(
            content=audio_bytes,
            media_type=media_type,
            headers={
                "Cache-Control": "no-cache",
                "X-Audio-Format": audio_format,
                "X-TTS-Cache": "HIT-L1",
            },
        )

    # Cache miss — synthesize
    try:
        payload = {
            "input": req.text,
            "voice": req.voice,
            "speed": req.speed,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{TTS_SERVICE_URL}/v1/audio/speech",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code != 200:
                logger.error(f"Piper TTS failed ({response.status_code}): {response.text}")
                redis_client.record_tts_error()
                raise HTTPException(status_code=502, detail="TTS service unavailable")

            audio_bytes = response.content

        synth_ms = (time.perf_counter() - t0) * 1000.0
        audio_format, media_type = detect_audio_format(audio_bytes)

        # Store in Redis (L2) and in-process (L1)
        redis_client.set_tts_cache(cache_key, audio_bytes, ttl=TTS_CACHE_TTL)
        _tts_l1_cache[cache_key] = (audio_bytes, media_type, audio_format)
        if len(_tts_l1_cache) > _TTS_L1_MAX_ITEMS:
            _tts_l1_cache.pop(next(iter(_tts_l1_cache)), None)

        redis_client.record_tts_miss(synth_ms)
        logger.debug("TTS synthesized in %.0f ms, stored in Redis+L1", synth_ms)

        return Response(
            content=audio_bytes,
            media_type=media_type,
            headers={
                "Cache-Control": "no-cache",
                "X-Audio-Format": audio_format,
                "X-TTS-Cache": "MISS",
                "X-TTS-Synth-Ms": str(round(synth_ms)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        redis_client.record_tts_error()
        logger.error(f"TTS Proxy Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


@router.get("/tts/health")
async def tts_health():
    """Check if the Qwen TTS service is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{TTS_SERVICE_URL}/health")
            return {"status": "ok" if resp.status_code == 200 else "degraded", "tts_status": resp.status_code}
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


@router.get("/tts/metrics")
async def tts_metrics():
    """Return TTS Redis cache performance counters (hits, misses, avg synthesis latency)."""
    from redis_client import redis_client
    return redis_client.get_tts_metrics()
