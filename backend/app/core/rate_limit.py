"""Redis fixed-window rate limiter and client IP resolution.

One counter per (scope, client IP, minute): ``INCR`` + ``EXPIRE`` in one transaction.
A fixed window can let up to 2x the limit through across a window boundary; that is
acceptable for abuse protection here.

Redis down: public routes fail open (serve the request, log a warning); login fails
closed (503) so a Redis outage cannot be used to brute-force credentials.
"""

from __future__ import annotations

import ipaddress
import time

from redis.asyncio import Redis

WINDOW_SECONDS = 60


def _is_trusted(ip: str, trusted: list[str]) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in ipaddress.ip_network(net, strict=False) for net in trusted)


def client_ip(peer: str | None, forwarded_for: str | None, trusted_proxies: list[str]) -> str:
    """Client IP for rate limiting.

    ``X-Forwarded-For`` is only honoured when the direct peer is a trusted proxy; otherwise
    any client could spoof it. Walk it right-to-left and return the first untrusted hop
    (the left-most entries are client-controlled).
    """
    ip = peer or "unknown"
    if not forwarded_for or not _is_trusted(ip, trusted_proxies):
        return ip
    for hop in reversed([h.strip() for h in forwarded_for.split(",") if h.strip()]):
        ip = hop
        if not _is_trusted(hop, trusted_proxies):
            break
    return ip


def _window_key(key: str, window_seconds: int, now: int) -> str:
    return f"ratelimit:{key}:{window_seconds}:{now // window_seconds}"


async def hit(redis: Redis, key: str, window_seconds: int = WINDOW_SECONDS) -> tuple[int, int]:
    """Count one request. Returns ``(count_in_window, window_reset_epoch)``. Raises ``RedisError``."""
    now = int(time.time())
    window_key = _window_key(key, window_seconds, now)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(window_key)
        pipe.expire(window_key, window_seconds)
        count, _ = await pipe.execute()
    return int(count), (now // window_seconds + 1) * window_seconds


async def reset(redis: Redis, key: str, window_seconds: int = WINDOW_SECONDS) -> None:
    """Clear the current window's counter for ``key``. Raises ``RedisError``."""
    await redis.delete(_window_key(key, window_seconds, int(time.time())))
