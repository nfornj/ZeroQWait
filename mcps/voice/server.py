"""
ZeroQwait Voice MCP Gateway
============================
Single gateway for all voice operations.  Runs as both:

  1. A FastAPI REST service (used by ZeroQwait backend and any HTTP client)
       POST /v1/audio/speech  — OpenAI-compatible TTS  (proxies to Qwen3-TTS)
       POST /transcribe       — Whisper-compatible ASR  (proxies to asr-service)
       GET  /health           — Aggregate health of TTS + ASR

  2. An MCP server (for Claude Desktop, VS Code, and any MCP-compatible client)
       Available via:  mcp run voice_mcp/server.py        (stdio)
                       GET /mcp/sse                       (SSE transport, if mounted)
       Tools: text_to_speech, transcribe_audio, voice_health

Configuration (env vars)
------------------------
TTS_UPSTREAM_URL   Qwen3-TTS service  (default: http://tts-service.zeroqwait.svc.cluster.local:8880)
ASR_UPSTREAM_URL   Whisper ASR base   (default: http://asr-service.zeroqwait.svc.cluster.local:8000)
TTS_DEFAULT_VOICE  Voice name         (default: Vivian)
HOST               Bind address       (default: 0.0.0.0)
PORT               Listen port        (default: 8881)
"""

import asyncio
import base64
import logging
import os

import httpx
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-mcp-gateway")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TTS_UPSTREAM = os.getenv(
    "TTS_UPSTREAM_URL",
    "http://tts-service.zeroqwait.svc.cluster.local:8880",
)
ASR_UPSTREAM = os.getenv(
    "ASR_UPSTREAM_URL",
    "http://asr-service.zeroqwait.svc.cluster.local:8000",
)
DEFAULT_VOICE = os.getenv("TTS_DEFAULT_VOICE", "Vivian")

# Shared async HTTP client — persistent connection pool across all requests
_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http


# ---------------------------------------------------------------------------
# Core logic — shared between REST endpoints and MCP tools
# ---------------------------------------------------------------------------

async def _do_tts(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
    language: str = "English",
) -> bytes:
    """Forward TTS request to Qwen3-TTS upstream, return raw WAV bytes."""
    payload = {
        "model": "tts-1-en",
        "input": text.strip(),
        "voice": voice,
        "speed": speed,
        "language": language,
        "instruct": (
            "Speak clearly and naturally with a warm, confident North American "
            "English accent. Enunciate each word precisely. Friendly and professional tone."
        ),
        "response_format": "wav",
    }
    resp = await _client().post(
        f"{TTS_UPSTREAM}/v1/audio/speech",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.content


async def _do_asr(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    mime_type: str = "audio/wav",
) -> dict:
    """Forward audio to Whisper ASR upstream, return transcription JSON."""
    files = {"file": (filename, audio_bytes, mime_type)}
    resp = await _client().post(
        f"{ASR_UPSTREAM}/transcribe",
        files=files,
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# FastAPI REST API  (ZeroQwait backend + any HTTP client)
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ZeroQwait Voice MCP Gateway",
    description=(
        "Single voice gateway: TTS (Qwen3-TTS/Vivian) + ASR (Whisper). "
        "REST-compatible with the original TTS and ASR service APIs so the "
        "backend can redirect to this service with a URL change only."
    ),
    version="1.0.0",
)


class SpeechRequest(BaseModel):
    model: str = "tts-1-en"
    input: str
    voice: str = DEFAULT_VOICE
    speed: float = 1.0
    response_format: str = "wav"
    # Forwarded to Qwen3-TTS (already stripped/ignored by older clients)
    language: str = "English"
    instruct: str = ""


@app.post(
    "/v1/audio/speech",
    summary="Text-to-Speech (OpenAI-compatible, routes to Qwen3-TTS)",
    response_class=Response,
)
async def rest_tts(req: SpeechRequest):
    if not req.input or not req.input.strip():
        raise HTTPException(status_code=400, detail="input text is empty")
    try:
        audio_bytes = await _do_tts(req.input, req.voice, req.speed, req.language)
    except httpx.HTTPStatusError as exc:
        logger.error("TTS upstream %s: %s", exc.response.status_code, exc.response.text[:200])
        raise HTTPException(status_code=502, detail="TTS upstream error")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="TTS upstream timed out")
    except Exception as exc:
        logger.error("TTS request failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    return Response(content=audio_bytes, media_type="audio/wav")


@app.post(
    "/transcribe",
    summary="Speech-to-Text (Whisper ASR-compatible)",
)
async def rest_transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    try:
        result = await _do_asr(
            audio_bytes,
            file.filename or "audio.wav",
            file.content_type or "audio/wav",
        )
    except httpx.HTTPStatusError as exc:
        logger.error("ASR upstream %s: %s", exc.response.status_code, exc.response.text[:200])
        raise HTTPException(status_code=502, detail="ASR upstream error")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ASR upstream timed out")
    except Exception as exc:
        logger.error("ASR request failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@app.get("/health", summary="Aggregate health — TTS + ASR")
async def health():
    status: dict = {"voice_mcp": "ok"}

    try:
        r = await _client().get(f"{TTS_UPSTREAM}/health", timeout=10.0)
        status["tts"] = r.json() if r.status_code == 200 else {"status": "error", "code": r.status_code}
    except Exception as exc:
        status["tts"] = {"status": "unreachable", "error": str(exc)}

    try:
        r = await _client().get(f"{ASR_UPSTREAM}/health", timeout=10.0)
        status["asr"] = r.json() if r.status_code == 200 else {"status": "error", "code": r.status_code}
    except Exception as exc:
        status["asr"] = {"status": "unreachable", "error": str(exc)}

    # Derive overall status
    tts_ok = isinstance(status.get("tts"), dict) and status["tts"].get("status") == "healthy"
    asr_ok = isinstance(status.get("asr"), dict) and status["asr"].get("status") == "ok"
    status["overall"] = "healthy" if (tts_ok and asr_ok) else "degraded"
    return status


# ---------------------------------------------------------------------------
# MCP tools — same core logic, exposed for external MCP clients
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        name="zeroqwait-voice",
        instructions=(
            "ZeroQwait Voice tools — TTS (Qwen3-TTS/Vivian) and ASR (Whisper). "
            "Accessible by any MCP-compatible client."
        ),
    )

    @mcp.tool(
        description=(
            "Convert text to speech using Qwen3-TTS (Vivian voice). "
            "Returns base64-encoded WAV audio and the voice used."
        )
    )
    async def text_to_speech(
        text: str,
        voice: str = DEFAULT_VOICE,
        speed: float = 1.0,
        language: str = "English",
    ) -> dict:
        if not text or not text.strip():
            return {"error": "text is empty"}
        try:
            audio_bytes = await _do_tts(text, voice, speed, language)
            return {
                "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
                "audio_format": "wav",
                "voice": voice,
                "char_count": len(text),
            }
        except Exception as exc:
            return {"error": str(exc)}

    @mcp.tool(
        description=(
            "Transcribe audio to text using Whisper ASR. "
            "Pass base64-encoded WAV or WebM audio bytes."
        )
    )
    async def transcribe_audio(
        audio_base64: str,
        filename: str = "audio.wav",
        mime_type: str = "audio/wav",
    ) -> dict:
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception:
            return {"error": "audio_base64 is not valid base64"}
        try:
            return await _do_asr(audio_bytes, filename, mime_type)
        except Exception as exc:
            return {"error": str(exc)}

    @mcp.tool(description="Check health of TTS (Qwen3-TTS) and ASR (Whisper) services.")
    async def voice_health() -> dict:
        results: dict = {}
        try:
            r = await _client().get(f"{TTS_UPSTREAM}/health", timeout=10.0)
            results["tts"] = r.json()
        except Exception as exc:
            results["tts"] = {"status": "unreachable", "error": str(exc)}
        try:
            r = await _client().get(f"{ASR_UPSTREAM}/health", timeout=10.0)
            results["asr"] = r.json()
        except Exception as exc:
            results["asr"] = {"status": "unreachable", "error": str(exc)}
        return results

    # Mount MCP SSE transport at /mcp/sse so external clients can connect via HTTP
    # as well as stdio (mcp run server.py).
    try:
        app.mount("/mcp", mcp.sse_app())
        logger.info("MCP SSE endpoint mounted at /mcp/sse — external clients can connect there.")
    except AttributeError:
        # Older builds of FastMCP don't expose sse_app() — MCP is still available via stdio.
        logger.info(
            "FastMCP.sse_app() not available in this build. "
            "Run 'mcp run voice_mcp/server.py' to use MCP tools via stdio."
        )

    logger.info("FastMCP tools registered: text_to_speech, transcribe_audio, voice_health")

except ImportError:
    logger.warning("mcp package not installed — MCP tool interface disabled. REST API still active.")


# ---------------------------------------------------------------------------
# Entry point (REST service)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8881"))
    logger.info("Starting ZeroQwait Voice MCP Gateway on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
