import os
import redis
import json
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        # Support both REDIS_URL and individual components (for K8s deployments)
        redis_url = os.getenv("REDIS_URL")
        
        if not redis_url:
            # Construct URL from components
            host = os.getenv("REDIS_HOST", "localhost")
            port = os.getenv("REDIS_PORT", "6379")
            password = os.getenv("REDIS_PASSWORD", "")
            
            if password:
                redis_url = f"redis://:{password}@{host}:{port}/0"
            else:
                redis_url = f"redis://{host}:{port}/0"
        
        self.redis_url = redis_url
        self.client = None
        self.enabled = False
        
        try:
            self.client = redis.from_url(
                self.redis_url, 
                decode_responses=True, 
                socket_timeout=5, 
                socket_connect_timeout=5
            )
            self.client.ping()
            self.enabled = True
            safe_url = self.redis_url.split("@")[-1] if "@" in self.redis_url else self.redis_url
            logger.info(f"Connected to Redis at {safe_url}. Caching ENABLED.")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching DISABLED.")
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

    # --- Rate Limiting ---
    
    def check_rate_limit(self, ip: str, limit: int = 20, window: int = 60) -> bool:
        """Sliding window / token bucket rate limiter using Redis."""
        if not self.enabled:
            return True  # Fail open if Redis is down
        try:
            key = f"rate_limit:{ip}"
            current = self.client.get(key)
            if current and int(current) >= limit:
                return False
            
            p = self.client.pipeline()
            p.incr(key)
            if not current:
                p.expire(key, window)
            p.execute()
            return True
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            return True  # Fail open on error

# Global instance
redis_client = RedisClient()
