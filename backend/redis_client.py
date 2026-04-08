import os
import redis
import json
import time
from typing import Optional, Any, List
import logging

logger = logging.getLogger(__name__)


def _tenant_key(shop_id: int, key: str) -> str:
    """Build a namespaced Redis key for a premium tenant."""
    return f"t:{shop_id}:{key}"


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
            # Binary client for audio bytes (TTS cache)
            self._bin_client = redis.from_url(
                self.redis_url,
                decode_responses=False,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching DISABLED.")
            self.client = None
            self._bin_client = None
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

    # ── Tenant-scoped operations (premium shops) ────────────────────

    def tenant_get(self, shop_id: int, key: str) -> Optional[Any]:
        """Get a value from a tenant's isolated namespace."""
        return self.get(_tenant_key(shop_id, key))

    def tenant_set(self, shop_id: int, key: str, value: Any, ttl: int = 300) -> bool:
        """Set a value in a tenant's isolated namespace."""
        return self.set(_tenant_key(shop_id, key), value, ttl)

    def tenant_delete(self, shop_id: int, key: str):
        """Delete a key from a tenant's namespace."""
        self.delete(_tenant_key(shop_id, key))

    def tenant_keys(self, shop_id: int, pattern: str = "*") -> List[str]:
        """List keys in a tenant's namespace. Returns keys with prefix stripped."""
        if not self.enabled:
            return []
        try:
            prefix = f"t:{shop_id}:"
            full_pattern = f"{prefix}{pattern}"
            raw_keys = self.client.keys(full_pattern)
            return [k.removeprefix(prefix) for k in raw_keys]
        except Exception as e:
            logger.error(f"Redis tenant_keys error for shop {shop_id}: {e}")
            return []

    def tenant_flush(self, shop_id: int) -> int:
        """Delete ALL keys for a tenant. Used during downgrade to free tier.
        Returns the number of keys deleted."""
        if not self.enabled:
            return 0
        try:
            prefix = f"t:{shop_id}:"
            keys = self.client.keys(f"{prefix}*")
            if keys:
                count = self.client.delete(*keys)
                logger.info("Flushed %d Redis keys for tenant shop %d", count, shop_id)
                return count
            return 0
        except Exception as e:
            logger.error(f"Redis tenant_flush error for shop {shop_id}: {e}")
            return 0

    # ── Tenant queue cache ──────────────────────────────────────────

    def set_queue_cache(self, shop_id: int, queue_data: dict, ttl: int = 30) -> bool:
        """Cache active queue state for a premium shop (30s default TTL)."""
        return self.tenant_set(shop_id, "queue:active", queue_data, ttl)

    def get_queue_cache(self, shop_id: int) -> Optional[dict]:
        """Get cached queue state for a premium shop."""
        return self.tenant_get(shop_id, "queue:active")

    def invalidate_queue_cache(self, shop_id: int):
        """Invalidate queue cache when queue changes (join, call-next, etc.)."""
        self.tenant_delete(shop_id, "queue:active")

    # ── Tenant analytics cache ──────────────────────────────────────

    def set_analytics_cache(self, shop_id: int, analytics: dict, ttl: int = 60) -> bool:
        """Cache analytics data for a premium shop (60s default TTL)."""
        return self.tenant_set(shop_id, "analytics:today", analytics, ttl)

    def get_analytics_cache(self, shop_id: int) -> Optional[dict]:
        """Get cached analytics for a premium shop."""
        return self.tenant_get(shop_id, "analytics:today")

    # ── Tenant services cache ───────────────────────────────────────

    def set_services_cache(self, shop_id: int, services: list, ttl: int = 300) -> bool:
        """Cache services list for a premium shop (5min default TTL)."""
        return self.tenant_set(shop_id, "services", services, ttl)

    def get_services_cache(self, shop_id: int) -> Optional[list]:
        """Get cached services list for a premium shop."""
        return self.tenant_get(shop_id, "services")

    # ── Tenant config ───────────────────────────────────────────────

    def set_shop_config(self, shop_id: int, config: dict) -> bool:
        """Store shop-specific config in Redis (1hr TTL)."""
        return self.tenant_set(shop_id, "config", config, ttl=3600)

    def get_shop_config(self, shop_id: int) -> Optional[dict]:
        """Get shop-specific config from Redis."""
        return self.tenant_get(shop_id, "config")

    # ── Tenant stats helper ─────────────────────────────────────────

    def get_tenant_stats(self, shop_id: int) -> dict:
        """Get a summary of a tenant's Redis footprint."""
        if not self.enabled:
            return {"shop_id": shop_id, "key_count": 0, "keys": []}
        keys = self.tenant_keys(shop_id)
        return {
            "shop_id": shop_id,
            "key_count": len(keys),
            "keys": keys,
        }

    # ── TTS audio cache ─────────────────────────────────────────────
    # Keys: tts:audio:<sha256>
    # Value: raw WAV bytes (binary-safe via _bin_client)
    # TTL: configurable, default 24 h (86400 s)
    # Metrics keys: tts:metrics:hits / tts:metrics:misses / tts:metrics:errors
    #               tts:metrics:latency_total_ms / tts:metrics:latency_count
    # All metric keys persist indefinitely; counters grow monotonically for
    # scraping via the /api/voice/tts/metrics endpoint.

    _TTS_CACHE_PREFIX = "tts:audio:"
    _TTS_DEFAULT_TTL_SECONDS = 86_400  # 24 hours

    def get_tts_cache(self, cache_key: str) -> Optional[bytes]:
        """Return cached WAV bytes for *cache_key*, or None on miss / error."""
        if not self.enabled or self._bin_client is None:
            return None
        try:
            data = self._bin_client.get(f"{self._TTS_CACHE_PREFIX}{cache_key}")
            return data  # bytes or None
        except Exception as exc:
            logger.debug("TTS cache GET error: %s", exc)
            return None

    def set_tts_cache(
        self, cache_key: str, audio_bytes: bytes, ttl: int = _TTS_DEFAULT_TTL_SECONDS
    ) -> bool:
        """Store *audio_bytes* under *cache_key* with *ttl* seconds expiry."""
        if not self.enabled or self._bin_client is None:
            return False
        try:
            self._bin_client.setex(
                f"{self._TTS_CACHE_PREFIX}{cache_key}", ttl, audio_bytes
            )
            return True
        except Exception as exc:
            logger.debug("TTS cache SET error: %s", exc)
            return False

    def record_tts_hit(self, latency_ms: float) -> None:
        """Increment TTS cache-hit counter and accumulate latency."""
        if not self.enabled:
            return
        try:
            p = self.client.pipeline()
            p.incr("tts:metrics:hits")
            p.incrbyfloat("tts:metrics:latency_saved_ms", latency_ms)
            p.execute()
        except Exception:
            pass

    def record_tts_miss(self, latency_ms: float) -> None:
        """Increment TTS cache-miss counter and accumulate synthesis latency."""
        if not self.enabled:
            return
        try:
            p = self.client.pipeline()
            p.incr("tts:metrics:misses")
            p.incrbyfloat("tts:metrics:latency_total_ms", latency_ms)
            p.incr("tts:metrics:latency_count")
            p.execute()
        except Exception:
            pass

    def record_tts_error(self) -> None:
        """Increment TTS error counter."""
        if not self.enabled:
            return
        try:
            self.client.incr("tts:metrics:errors")
        except Exception:
            pass

    def get_tts_metrics(self) -> dict:
        """Return a snapshot of TTS cache performance counters."""
        if not self.enabled:
            return {"enabled": False}
        try:
            keys = [
                "tts:metrics:hits",
                "tts:metrics:misses",
                "tts:metrics:errors",
                "tts:metrics:latency_total_ms",
                "tts:metrics:latency_count",
                "tts:metrics:latency_saved_ms",
            ]
            vals = self.client.mget(keys)
            hits = int(vals[0] or 0)
            misses = int(vals[1] or 0)
            errors = int(vals[2] or 0)
            lat_total = float(vals[3] or 0)
            lat_count = int(vals[4] or 0)
            lat_saved = float(vals[5] or 0)
            total = hits + misses
            hit_rate = round(hits / total, 4) if total else 0.0
            avg_synth_ms = round(lat_total / lat_count, 1) if lat_count else None
            return {
                "enabled": True,
                "hits": hits,
                "misses": misses,
                "errors": errors,
                "total": total,
                "hit_rate": hit_rate,
                "avg_synthesis_ms": avg_synth_ms,
                "total_latency_saved_ms": round(lat_saved, 1),
            }
        except Exception as exc:
            logger.debug("TTS metrics read error: %s", exc)
            return {"enabled": True, "error": str(exc)}


# Global instance
redis_client = RedisClient()
