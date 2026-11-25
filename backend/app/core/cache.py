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

# A detail read that overlaps a write must not refill a key the write just deleted.
_SET_IF_CURRENT = """
local version = redis.call('GET', KEYS[1]) or '0'
if version == ARGV[1] then
    redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
end
"""


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
    validate: Callable[[Any], Any] = lambda value: value,
    version_key: str | None = None,
) -> tuple[Any, bool]:
    """Return ``(value, hit)``. ``value`` must be JSON-serialisable.

    Empty values are cached too (with ``empty_ttl``) so repeated empty lookups skip the DB.
    """
    if ttl == 0:
        return await loader(), False

    try:
        cached = await redis.get(key)
        if cached is not None:
            return validate(json.loads(cached)), True
    except (RedisError, ValueError) as exc:
        logger.warning("cache get failed", extra={"key": key, "error": str(exc)})

    version = await get_version(redis, version_key) if version_key is not None else None
    value = await loader()
    entry_ttl = empty_ttl if is_empty(value) else ttl
    if entry_ttl > 0:
        try:
            payload = json.dumps(value)
            expiry = _jitter(entry_ttl)
            if version_key is None:
                await redis.set(key, payload, ex=expiry)
            elif version is not None:
                await redis.eval(_SET_IF_CURRENT, 2, version_key, key, version, payload, expiry)
        except RedisError as exc:
            logger.warning("cache set failed", extra={"key": key, "error": str(exc)})
    return value, False


async def get_version(redis: Redis, key: str) -> int | None:
    """Current namespace version, or None when it cannot be read."""
    try:
        return int(await redis.get(key) or 0)
    except (RedisError, ValueError) as exc:
        logger.warning("cache version read failed", extra={"key": key, "error": str(exc)})
        return None


async def invalidate(redis: Redis, version_key: str, *keys: str) -> None:
    """Bump the namespace version (O(1), no key scans) and delete ``keys`` directly."""
    try:
        await redis.incr(version_key)
    except RedisError as exc:
        logger.warning("cache version bump failed", extra={"key": version_key, "error": str(exc)})

    if keys:
        try:
            await redis.delete(*keys)
        except RedisError as exc:
            logger.warning("cache delete failed", extra={"keys": keys, "error": str(exc)})
