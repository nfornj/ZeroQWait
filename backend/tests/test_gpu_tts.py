#!/usr/bin/env python3
"""
Phase 6 test: GPU TTS service health + synthesis.

Confirms:
1. TTS service is reachable and /health returns 200
2. POST /v1/audio/speech returns audio bytes with Vivian voice
3. Response is valid WAV audio
"""

import io
import os
import wave
import pytest
import requests

TTS_URL = os.getenv("TTS_SERVICE_URL", "http://localhost:30880")
BACKEND_URL = os.getenv("TEST_BASE_URL", "http://localhost:30000")


def test_tts_health():
    """TTS /health returns 200 with status=ok."""
    r = requests.get(f"{TTS_URL}/health", timeout=30)
    assert r.status_code == 200, f"TTS health failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("status") == "ok", f"TTS not ok: {data}"
    assert data.get("voice") == "Vivian", f"Wrong voice: {data.get('voice')}"


def test_tts_backend_proxy_health():
    """Backend /api/voice/tts/health proxies TTS service."""
    r = requests.get(f"{BACKEND_URL}/api/voice/tts/health", timeout=30)
    assert r.status_code == 200, f"Backend TTS health proxy failed: {r.status_code}"


def test_tts_synthesis_returns_audio():
    """POST /v1/audio/speech returns audio bytes."""
    r = requests.post(
        f"{TTS_URL}/v1/audio/speech",
        json={
            "input": "Hello, I am Vivian from ZeroQwait.",
            "voice": "Vivian",
            "speed": 1.0,
            "language": "English",
            "model": "tts-1-en",
        },
        timeout=60,
    )
    assert r.status_code == 200, f"TTS synthesis failed: {r.status_code} {r.text}"
    assert len(r.content) > 1000, "Response too small to be valid audio"


def test_tts_synthesis_is_valid_wav():
    """Synthesized audio should be a valid WAV file."""
    r = requests.post(
        f"{TTS_URL}/v1/audio/speech",
        json={"input": "Test audio.", "voice": "Vivian"},
        timeout=60,
    )
    assert r.status_code == 200
    buf = io.BytesIO(r.content)
    try:
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1, "Expected mono audio"
            assert wf.getsampwidth() == 2, "Expected 16-bit audio"
            assert wf.getframerate() > 0, "Invalid sample rate"
    except wave.Error as exc:
        pytest.fail(f"Response is not valid WAV: {exc}")


def test_tts_via_backend_proxy():
    """POST /api/voice/tts (backend proxy) returns audio."""
    r = requests.post(
        f"{BACKEND_URL}/api/voice/tts",
        json={"text": "Testing the backend TTS proxy.", "voice": "Vivian"},
        timeout=60,
    )
    assert r.status_code == 200, f"Backend /api/voice/tts failed: {r.status_code} {r.text}"
    assert len(r.content) > 1000, "Proxied TTS response too small"


def test_tts_voice_header():
    """Response should include X-Voice: Vivian header."""
    r = requests.post(
        f"{TTS_URL}/v1/audio/speech",
        json={"input": "Voice header test.", "voice": "Vivian"},
        timeout=60,
    )
    assert r.status_code == 200
    assert r.headers.get("X-Voice") == "Vivian", \
        f"Missing X-Voice header. Got: {dict(r.headers)}"


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
