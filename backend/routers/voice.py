import httpx
import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

ASR_SERVICE_URL = os.getenv("ASR_SERVICE_URL", "http://asr-service.zeroqwait.svc.cluster.local:8000/transcribe")
# TTS service - running on the host machine port 8880
TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", "http://192.168.2.88:8880")

class TTSRequest(BaseModel):
    text: str
    voice: str = "serena"      # Voice profile (e.g., serena, eric, ryan)
    speed: float = 1.0         # 1.0 = normal

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
    Returns buffered MP3 audio for the frontend to play.
    """
    try:
        payload = {
            "model": "tts-1",
            "input": req.text,
            "voice": req.voice,
            "speed": req.speed,
            "response_format": "mp3"
        }
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{TTS_SERVICE_URL}/v1/audio/speech",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code != 200:
                logger.error(f"Qwen TTS failed ({response.status_code}): {response.text}")
                raise HTTPException(status_code=502, detail="TTS service unavailable")
            
            audio_bytes = response.content

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache"}
        )

    except HTTPException:
        raise
    except Exception as e:
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
