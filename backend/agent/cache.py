"""
Sentence-transformer embedder and semantic query cache.
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

from agent.config import model

# --- Smart Query Processor ---

from dataclasses import dataclass
import numpy as np

embedder = None

def get_embedder():
    global embedder
    if embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load embedder: {e}")
    return embedder

class SemanticCache:
    """Lightweight semantic cache using sentence-transformers."""
    def __init__(self, threshold=0.92):
        self.threshold = threshold
        self.local_cache = []  # List of (embedding_vector, IntentAnalysis_dict)
    
    def get(self, query: str) -> Optional[dict]:
        if not query.strip() or not self.local_cache:
            return None
        try:
            embedder_inst = get_embedder()
            if not embedder_inst:
                return None
            vec = embedder_inst.encode([query.strip().lower()])[0]
            norm = np.linalg.norm(vec)
            if norm == 0:
                return None
            normed_vec = vec / norm
            
            # Batch cosine similarity — pre-normalized vectors
            cached_vecs = np.array([v for v, _ in self.local_cache])
            scores = cached_vecs @ normed_vec
            best_idx = int(np.argmax(scores))
            best_score = scores[best_idx]
                    
            if best_score >= self.threshold:
                logger.debug(f"Semantic Cache Hit! Score: {best_score:.3f}")
                return self.local_cache[best_idx][1]
            return None
        except Exception as e:
            logger.error(f"Semantic cache error: {e}")
            return None
            
    def set(self, query: str, result_dict: dict):
        try:
            embedder_inst = get_embedder()
            if not embedder_inst:
                return
            vec = embedder_inst.encode([query.strip().lower()])[0]
            norm = np.linalg.norm(vec)
            if norm == 0:
                return
            normed_vec = vec / norm
            self.local_cache.append((normed_vec, result_dict))
            # Keep cache from growing infinitely
            if len(self.local_cache) > 1000:
                self.local_cache = self.local_cache[-1000:]
        except Exception as e:
            logger.error(f"Failed to set cache: {e}")

semantic_cache = SemanticCache()

# Eagerly initialize the embedder at module load time so the sentence-transformer model
# is downloaded before any request arrives (avoids a 60-90s stall on first request).
try:
    get_embedder()
    logger.info("Sentence-transformer embedder pre-loaded successfully.")
except Exception as _e:
    logger.warning(f"Embedder pre-load failed (non-fatal, will retry on first request): {_e}")


