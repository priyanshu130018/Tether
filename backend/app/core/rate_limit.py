import time
from collections import defaultdict
from threading import Lock

from app.core.config import get_settings

settings = get_settings()

# In-memory sliding window rate limiter fallback
_local_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_store_lock = Lock()


def check_rate_limit(
    key: str,
    limit: int | None = None,
    window_seconds: int = 60,
    redis_client=None,
) -> bool:
    """
    Check if a rate limit has been exceeded.
    Returns True if the request is ALLOWED, False if RATE LIMITED.
    """
    effective_limit = limit if limit is not None else settings.auth_rate_limit_per_minute
    now = time.time()

    # If redis client is provided and available
    if redis_client:
        try:
            redis_key = f"ratelimit:{key}"
            member_id = f"{now}:{time.perf_counter_ns()}"
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
            pipe.zadd(redis_key, {member_id: now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window_seconds + 5)
            results = pipe.execute()
            count = results[2]
            return count <= effective_limit
        except Exception:
            pass  # Fall back to in-memory

    # In-memory sliding window fallback
    with _store_lock:
        timestamps = _local_rate_limit_store[key]
        cutoff = now - window_seconds
        # Retain only timestamps within the window
        timestamps = [ts for ts in timestamps if ts > cutoff]
        if len(timestamps) >= effective_limit:
            _local_rate_limit_store[key] = timestamps
            return False
        timestamps.append(now)
        _local_rate_limit_store[key] = timestamps
        return True


def clear_rate_limits() -> None:
    """Utility to reset rate limits (helpful in tests)."""
    with _store_lock:
        _local_rate_limit_store.clear()
