"""
Precompiled regex patterns, helper functions, and TTS client state.
"""
import os
import re
import json
import logging
import asyncio
import httpx
import base64
from typing import List, Optional, Dict, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from db_interface import db_interface
from redis_client import redis_client
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

logger = logging.getLogger(__name__)


# --- Precompiled Regex for Hot Paths ---
# Split on sentence-ending punctuation, but NOT after digit-dot (e.g. "1." "2." "3.")
_SENTENCE_BOUNDARY_RE = re.compile(r'(?<!\d[.])(?<=[.?!])\s+')
_MARKDOWN_BOLD_RE = re.compile(r'\*\*(.*?)\*\*')
_MARKDOWN_ITALIC_RE = re.compile(r'\*(.*?)\*')
_MARKDOWN_HEADING_RE = re.compile(r'#{1,6}\s')
_MARKDOWN_CODE_RE = re.compile(r'`([^`]*)`')
_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_EMOJI_RE = re.compile(
    r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
    r'\U0001F1E0-\U0001F1FF\U00002600-\U000026FF\U00002700-\U000027BF'
    r'\U0000FE00-\U0000FE0F\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F'
    r'\U0001FA70-\U0001FAFF\U0000200D\U000020E3\U000E0020-\U000E007F]'
)
_WHITESPACE_MULTI_RE = re.compile(r'\s{2,}')

# Registration cancellation — used inside active-registration block (Redis state check)
_CANCEL_REGISTRATION_RE = re.compile(
    r'(?:cancel|stop|quit|abort|nevermind|never\s*mind|start\s*over)',
    re.IGNORECASE
)
_REGISTRATION_INTERRUPT_INTENTS = {'SEARCH', 'PLATFORM_INFO', 'CONVERSATION'}

_QUEUE_JOIN_REQUEST_RE = re.compile(
    r'\b(join\s+(the\s+)?queue|check\s*in|enqueue|book\s+me|add\s+me)\b',
    re.IGNORECASE,
)
_APPOINTMENT_REQUEST_RE = re.compile(
    r'\b(appointment|schedule|book\s+(an?\s+)?appointment|reserve|make\s+a\s+booking|schedule\s+a\s+visit)\b',
    re.IGNORECASE,
)
_WAIT_TIME_REQUEST_RE = re.compile(
    r'\b(wait\s*time|how\s+long|eta|queue\s+status|position)\b',
    re.IGNORECASE,
)
_NAME_CAPTURE_RE = re.compile(
    r"(?:my\s+name\s+is|name\s+is|i\s+am|i'm)\s+([A-Za-z][A-Za-z\s'\-]{1,60}?)(?=\s+(?:and\s+)?phone\b|[.,;]|$)",
    re.IGNORECASE,
)
_PHONE_CAPTURE_RE = re.compile(
    r'(?:phone(?:\s+number)?\s*(?:is|:)?\s*)?([+]?\d[\d\s\-()]{6,20}\d)',
    re.IGNORECASE,
)

_TTS_TIMEOUT_SECONDS = 60.0


def _extract_customer_details_for_join(user_msg: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Best-effort extraction for queue join details from free text.
    
    Returns (name, phone, service_name).
    """
    name: Optional[str] = None
    phone: Optional[str] = None
    service_name: Optional[str] = None

    name_match = _NAME_CAPTURE_RE.search(user_msg)
    if name_match:
        name = _WHITESPACE_MULTI_RE.sub(' ', name_match.group(1)).strip(" .,")

    phone_match = _PHONE_CAPTURE_RE.search(user_msg)
    if phone_match:
        raw_phone = phone_match.group(1)
        phone = _WHITESPACE_MULTI_RE.sub(' ', raw_phone).strip()

    # Extract service name: "service is Haircut", "service is Hair Cut & Wash", etc.
    svc_match = re.search(
        r'service\s+(?:is|:)\s+([A-Za-z][A-Za-z &\-]+)',
        user_msg, re.IGNORECASE,
    )
    if svc_match:
        service_name = svc_match.group(1).strip(" .,")

    return name, phone, service_name


def _is_shop_queue_join_request(user_msg: str) -> bool:
    return bool(_QUEUE_JOIN_REQUEST_RE.search(user_msg))


def _is_appointment_request(user_msg: str) -> bool:
    return bool(_APPOINTMENT_REQUEST_RE.search(user_msg))


def _is_shop_wait_request(user_msg: str) -> bool:
    return bool(_WAIT_TIME_REQUEST_RE.search(user_msg))


def _build_queue_join_form_event(shop_id: int, shop_name: str, city: Optional[str] = None, shop_type: Optional[str] = None) -> Dict[str, Any]:
    """Generate a queue_join_form SSE event for inline form rendering in frontend."""
    # Fetch available services for this shop so frontend can show a dropdown
    services = []
    try:
        raw = db_interface.get_shop_services(shop_id)
        services = [
            {"id": s.get("id"), "name": s.get("name"), "cost": s.get("cost", 0)}
            for s in raw if s.get("name")
        ]
    except Exception:
        pass

    return {
        "type": "queue_join_form",
        "shop_id": shop_id,
        "shop_name": shop_name,
        "city": city,
        "shop_type": shop_type,
        "services": services,
        "status": "collecting",
    }


def _build_appointment_form_event(shop_id: int, shop_name: str) -> Dict[str, Any]:
    """Generate an appointment_form SSE event for inline appointment booking in frontend."""
    services = []
    try:
        raw = db_interface.get_shop_services(shop_id)
        services = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "cost": s.get("cost", 0),
                "duration_minutes": s.get("duration_minutes", 30),
            }
            for s in raw if s.get("name")
        ]
    except Exception:
        pass

    return {
        "type": "appointment_form",
        "shop_id": shop_id,
        "shop_name": shop_name,
        "services": services,
        "status": "collecting",
    }


# Shared httpx client for TTS (connection pooling)
_tts_client: Optional[httpx.AsyncClient] = None
_tts_cache: Dict[str, Tuple[str, str]] = {}
_TTS_CACHE_MAX_ITEMS = 256

def _get_tts_client() -> httpx.AsyncClient:
    global _tts_client
    if _tts_client is None or _tts_client.is_closed:
        _tts_client = httpx.AsyncClient(
            timeout=httpx.Timeout(_TTS_TIMEOUT_SECONDS, connect=10.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3)
        )
    return _tts_client

