import httpx
import os
from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter()

ASR_SERVICE_URL = os.getenv("ASR_SERVICE_URL", "http://asr-service.zeroqwait.svc.cluster.local:8000/transcribe")

@router.post("/transcribe")
async def transcribe_voice(file: UploadFile = File(...)):
    """
    Receives an audio file from the frontend, forwards it to the GPU-accelerated 
    ASR service, and returns the transcribed text.
    """
    try:
        # Read the file content
        file_content = await file.read()
        
        # Forward to ASR service
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {'file': (file.filename, file_content, file.content_type)}
            response = await client.post(ASR_SERVICE_URL, files=files)
            
            if response.status_code != 200:
                print(f"ASR Service Failed: {response.text}")
                raise HTTPException(status_code=502, detail="ASR Service unavailable")
                
            result = response.json()
            return result
            
    except Exception as e:
        print(f"Voice Transcription Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
