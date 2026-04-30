"""
Ollama / Pydantic-AI model configuration.
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
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from db_interface import db_interface
from redis_client import redis_client
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

logger = logging.getLogger(__name__)


# --- Configuration ---
ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
model_name = os.getenv("MODEL_NAME", "qwen3:14b-q4_K_M")

_llm_provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

if _llm_provider == "nvidia" and os.getenv("NVIDIA_API_KEY"):
    # Route customer-facing master agent through NVIDIA NIM
    _nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
    _nvidia_key = os.getenv("NVIDIA_API_KEY")
    logger.info("MasterAgent: using NVIDIA NIM model=%s", _nvidia_model)
    model = OpenAIChatModel(
        _nvidia_model,
        provider=OpenAIProvider(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=_nvidia_key,
        ),
    )
else:
    logger.info("MasterAgent: using Ollama model=%s url=%s", model_name, ollama_url)
    model = OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=ollama_url, api_key='ollama'),
    )


