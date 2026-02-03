import os
import shutil
import tempfile
import time
from typing import Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from faster_whisper import WhisperModel

app = FastAPI(title="ZeroQwait ASR Service", description="GPU-accelerated speech-to-text using faster-whisper")

# Configuration
MODEL_SIZE = os.getenv("MODEL_SIZE", "medium")
DEVICE = os.getenv("DEVICE", "cuda") # or "cpu"
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "float16" if DEVICE == "cuda" else "int8")

print(f"Loading Whisper Model: {MODEL_SIZE} on {DEVICE} ({COMPUTE_TYPE})...")
try:
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print("Model loaded successfully.")
except Exception as e:
    print(f"FAILED to load model: {e}")
    # In production, we might want to crash here, but for now we'll let the app start
    # and fail on requests so we can check logs.
    model = None

@app.get("/health")
def health_check():
    return {"status": "ok", "model_loaded": model is not None, "device": DEVICE}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not model:
        raise HTTPException(status_code=503, detail="ASR Model not loaded")

    start_time = time.time()
    
    # Save to temp file because faster-whisper needs a file path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        try:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
        except Exception as e:
            return {"error": f"Failed to save audio file: {str(e)}"}
    
    try:
        segments, info = model.transcribe(temp_path, beam_size=5)
        
        # Collect all segments (running the generator)
        full_text = " ".join([segment.text for segment in segments]).strip()
        
        duration = time.time() - start_time
        
        return {
            "text": full_text,
            "language": info.language,
            "probability": info.language_probability,
            "processing_time": round(duration, 3)
        }
    
    except Exception as e:
        print(f"Transcription Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
