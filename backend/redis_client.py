import os
import redis
import json
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client = None
        self.enabled = False
        
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
            self.enabled = True
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching will be disabled.")
            self.client = None
            self.enabled = False

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        try:
            val = self.client.get(key)
            if val:
                try:
                    return json.loads(val)
                except json.JSONDecodeError:
                    return val
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        if not self.enabled:
            return False
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            self.client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def delete(self, key: str):
        if self.enabled:
            try:
                self.client.delete(key)
            except Exception:
                pass

    # --- Session-Based Conversation Storage ---
    
    def get_session_history(self, session_id: str, limit: int = 10) -> list:
        """Retrieve the last N messages from a session."""
        if not self.enabled:
            return []
        try:
            key = f"session:{session_id}:history"
            # Get last `limit` messages (stored as JSON list)
            raw = self.client.lrange(key, -limit, -1)
            return [json.loads(msg) for msg in raw] if raw else []
        except Exception as e:
            logger.error(f"Redis get_session_history error: {e}")
            return []
    
    def add_session_message(self, session_id: str, role: str, content: str) -> bool:
        """Append a message to session history. Auto-expires after 24 hours."""
        if not self.enabled:
            return False
        try:
            key = f"session:{session_id}:history"
            message = json.dumps({"role": role, "content": content})
            self.client.rpush(key, message)
            # Keep only last 50 messages
            self.client.ltrim(key, -50, -1)
            # Set TTL to 24 hours
            self.client.expire(key, 86400)
            return True
        except Exception as e:
            logger.error(f"Redis add_session_message error: {e}")
            return False
    
    def clear_session(self, session_id: str) -> bool:
        """Clear all session data."""
        if not self.enabled:
            return False
        try:
            key = f"session:{session_id}:history"
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis clear_session error: {e}")
            return False

# Global instance
redis_client = RedisClient()
