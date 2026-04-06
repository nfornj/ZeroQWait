"""
Qwen3-TTS OpenAI-compatible API wrapper.

Exposes POST /v1/audio/speech compatible with the OpenAI TTS API,
backed by Qwen3-TTS-12Hz-1.7B-CustomVoice.
"""

import asyncio
import io
import os
import logging
import threading
import json
import re
import urllib.request

import torch
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qwen3-tts-service")

app = FastAPI(title="Qwen3-TTS Service")

MODEL_NAME = os.getenv("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
TTS_DEVICE = os.getenv("TTS_DEVICE", "gpu").lower()
TTS_WARMUP = os.getenv("TTS_WARMUP_ON_START", "true").lower() == "true"

# Global model reference and generation lock (GPU is single-threaded)
_model = None
_gen_lock = asyncio.Lock()
_model_load_error = None
_model_loading = False


def _ensure_missing_preprocessor_config(error_text: str) -> bool:
    """Create a minimal preprocessor_config.json when HF snapshot misses it."""
    if "preprocessor_config.json" not in error_text or "speech_tokenizer" not in error_text:
        return False


def _ensure_missing_speech_tokenizer_files(error_text: str) -> bool:
    """Download missing speech_tokenizer artifacts directly from HuggingFace when absent."""
    if "speech_tokenizer" not in error_text:
        return False

    match = re.search(r"'([^']+/speech_tokenizer)'", error_text)
    if not match:
        return False

    speech_tokenizer_dir = match.group(1)
    os.makedirs(speech_tokenizer_dir, exist_ok=True)

    base_url = f"https://huggingface.co/{MODEL_NAME}/resolve/main/speech_tokenizer"
    required = [
        "preprocessor_config.json",
        "model.safetensors",
    ]

    changed = False
    for filename in required:
        path = os.path.join(speech_tokenizer_dir, filename)
        if os.path.exists(path):
            continue
        url = f"{base_url}/{filename}"
        try:
            logger.warning("Downloading missing speech_tokenizer file: %s", url)
            with urllib.request.urlopen(url, timeout=300) as r:
                data = r.read()
            with open(path, "wb") as f:
                f.write(data)
            changed = True
        except Exception as dl_err:
            logger.error("Failed to download %s: %s", filename, dl_err, exc_info=True)
            return False

    return changed

    match = re.search(r"'([^']+/speech_tokenizer)'", error_text)
    if not match:
        return False

    speech_tokenizer_dir = match.group(1)
    config_path = os.path.join(speech_tokenizer_dir, "config.json")
    preproc_path = os.path.join(speech_tokenizer_dir, "preprocessor_config.json")

    if os.path.exists(preproc_path) or not os.path.exists(config_path):
        return False

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            tokenizer_cfg = json.load(f)

        sample_rate = tokenizer_cfg.get("input_sample_rate", 24000)
        preproc_cfg = {
            "feature_extractor_type": "Wav2Vec2FeatureExtractor",
            "sampling_rate": sample_rate,
            "padding_value": 0.0,
            "return_attention_mask": True,
            "do_normalize": False,
        }

        with open(preproc_path, "w", encoding="utf-8") as f:
            json.dump(preproc_cfg, f)

        logger.warning(
            "Created missing preprocessor_config.json at %s to recover tokenizer load",
            preproc_path,
        )
        return True
    except Exception as patch_err:
        logger.error("Failed to create fallback preprocessor config: %s", patch_err, exc_info=True)
        return False

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
    voice: str = "Vivian"
    speed: float = 1.0
    response_format: str = "wav"
    # Optional styling/language hints forwarded from the backend
    language: str = "English"
    instruct: str = ""


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
    logger.warning(f"Unknown voice '{voice}', falling back to Vivian")
    return "Vivian"


def _load_model_sync():
    global _model, _model_load_error, _model_loading
    from qwen_tts import Qwen3TTSModel

    device_map = "cuda:0" if TTS_DEVICE == "gpu" else "cpu"
    dtype = torch.bfloat16 if TTS_DEVICE == "gpu" else torch.float32

    try:
        logger.info(f"Loading Qwen3-TTS model: {MODEL_NAME} on {device_map}")
        try:
            _model = Qwen3TTSModel.from_pretrained(
                MODEL_NAME,
                device_map=device_map,
                dtype=dtype,
            )
        except Exception as first_err:
            err_text = str(first_err)
            patched = _ensure_missing_preprocessor_config(err_text)
            patched = _ensure_missing_speech_tokenizer_files(err_text) or patched
            if patched:
                logger.info("Retrying Qwen3-TTS model load after applying speech tokenizer file fixes")
                _model = Qwen3TTSModel.from_pretrained(
                    MODEL_NAME,
                    device_map=device_map,
                    dtype=dtype,
                )
            else:
                raise

        _model_load_error = None
        logger.info("Qwen3-TTS model loaded successfully")
    except Exception as e:
        _model_load_error = str(e)
        logger.error(f"Qwen3-TTS model load failed: {e}", exc_info=True)
    finally:
        _model_loading = False


def _warmup_model():
    """Fire a short inference after load to prime CUDA kernels, reducing cold-start latency."""
    if not TTS_WARMUP or _model is None:
        return
    try:
        logger.info("Warming up Qwen3-TTS model (CUDA kernel prime)...")
        _model.generate_custom_voice(text="Hello.", language="English", speaker="Vivian")
        logger.info("Warm-up complete.")
    except Exception as e:
        logger.warning(f"Warm-up failed (non-fatal): {e}")


def _load_model_and_warmup():
    _load_model_sync()
    _warmup_model()


@app.on_event("startup")
async def load_model():
    global _model_loading
    _model_loading = True
    threading.Thread(target=_load_model_and_warmup, daemon=True).start()


@app.get("/health")
async def health():
    if _model is not None:
        return {"status": "healthy"}
    if _model_load_error:
        return {"status": "error", "error": _model_load_error}
    if _model_loading:
        return {"status": "loading"}
    return {"status": "loading"}


@app.post("/v1/audio/speech")
async def create_speech(req: SpeechRequest):
    if _model is None:
        if _model_load_error:
            raise HTTPException(status_code=503, detail=f"Model load failed: {_model_load_error}")
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    text = (req.input or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Input text is empty")

    speaker = _resolve_speaker(req.voice)

    # Map request language to what the model accepts
    lang = req.language if req.language else "English"

    def _run_inference() -> bytes:
        """Run generate + encode entirely off the event loop to avoid CPU-spike blocking."""
        wavs, sr = _model.generate_custom_voice(
            text=text,
            language=lang,
            speaker=speaker,
        )
        buf = io.BytesIO()
        sf.write(buf, wavs[0], sr, format="WAV")
        return buf.getvalue()

    async with _gen_lock:
        try:
            audio_bytes = await asyncio.to_thread(_run_inference)
        except Exception as e:
            logger.error(f"TTS generation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=speech.wav"},
    )
