"""Cache-aside helper. Best-effort: if Redis fails, log a warning and use the loader.

Stampede: no lock. A hot key that expires may be loaded by several requests at once;
we accept that and spread expiries with TTL jitter so keys don't all expire together.
"""

from __future__ import annotations

import json
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

JITTER_RATIO = 0.1


def _jitter(ttl: int) -> int:
    return ttl + random.randint(0, int(ttl * JITTER_RATIO))  # noqa: S311 - not crypto


async def get_or_set(
    redis: Redis,
    key: str,
    loader: Callable[[], Awaitable[Any]],
    *,
    ttl: int,
    empty_ttl: int,
    is_empty: Callable[[Any], bool] = lambda value: not value,
) -> tuple[Any, bool]:
    """Return ``(value, hit)``. ``value`` must be JSON-serialisable.

    Empty values are cached too (with ``empty_ttl``) so repeated empty lookups skip the DB.
    """
    try:
        cached = await redis.get(key)
        if cached is not None:
            return json.loads(cached), True
    except RedisError as exc:
        logger.warning("cache get failed", extra={"key": key, "error": str(exc)})

    value = await loader()
    try:
        await redis.set(key, json.dumps(value), ex=_jitter(empty_ttl if is_empty(value) else ttl))
    except RedisError as exc:
        logger.warning("cache set failed", extra={"key": key, "error": str(exc)})
    return value, False


async def get_version(redis: Redis, key: str) -> int:
    """Current namespace version (0 if unset or Redis is down)."""
    try:
        return int(await redis.get(key) or 0)
    except RedisError as exc:
        logger.warning("cache version read failed", extra={"key": key, "error": str(exc)})
        return 0


async def invalidate(redis: Redis, version_key: str, *keys: str) -> None:
    """Bump the namespace version (O(1), no key scans) and delete ``keys`` directly."""
    try:
        await redis.incr(version_key)
        if keys:
            await redis.delete(*keys)
    except RedisError as exc:
        logger.warning("cache invalidation failed", extra={"key": version_key, "error": str(exc)})
