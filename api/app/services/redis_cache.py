import redis
import json
import logging
from typing import Any, Optional
from app.config import settings

logger = logging.getLogger("market-advisor-cache")

# Global Redis client
_redis_client: Optional[redis.Redis] = None

def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None  # force reconnect
    
    if not settings.redis_url:
        return None
        
    try:
        # Connect to redis using redis_url
        _redis_client = redis.Redis.from_url(
            settings.redis_url, 
            decode_responses=True,
            socket_timeout=2.0,  # 2s timeout for connection/operations
            socket_connect_timeout=2.0
        )
        # Test connection
        _redis_client.ping()
        logger.info("Connected to Redis server successfully.")
        return _redis_client
    except Exception as exc:
        logger.warning(f"Could not connect to Redis at {settings.redis_url}: {exc}. Caching is disabled.")
        _redis_client = None
        return None

def get_cache(key: str) -> Optional[Any]:
    client = get_redis_client()
    if not client:
        return None
    try:
        val = client.get(key)
        if val:
            return json.loads(val)
    except Exception as exc:
        logger.error(f"Error reading from Redis cache: {exc}")
    return None

def set_cache(key: str, data: Any, ttl: int = 3600) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.setex(key, ttl, json.dumps(data, default=str))
    except Exception as exc:
        logger.error(f"Error writing to Redis cache: {exc}")

def invalidate_cache(key: str) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.delete(key)
    except Exception as exc:
        logger.error(f"Error invalidating Redis cache key {key}: {exc}")

def invalidate_pattern(pattern: str) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
    except Exception as exc:
        logger.error(f"Error invalidating Redis cache pattern {pattern}: {exc}")

def invalidate_all_caches() -> None:
    invalidate_pattern("recommendations:*")
    invalidate_pattern("signals:*")
    invalidate_pattern("stock_detail:*")
