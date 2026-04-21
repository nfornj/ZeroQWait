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
model = OpenAIChatModel(
    model_name,
    provider=OpenAIProvider(base_url=ollama_url, api_key='ollama'),
)


