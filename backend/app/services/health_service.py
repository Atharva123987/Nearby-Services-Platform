"""Readiness: the database is required, Redis is best-effort."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.schemas.health import CheckStatus, DependencyCheck, ReadinessResponse, ReadyStatus

logger = logging.getLogger(__name__)


class DatabasePinger(Protocol):
    async def ping(self) -> None: ...


class CachePinger(Protocol):
    def ping(self) -> Awaitable[Any] | Any: ...


class HealthService:
    def __init__(self, db: DatabasePinger, cache: CachePinger, timeout_seconds: float) -> None:
        self._db = db
        self._cache = cache
        self._timeout = timeout_seconds

    async def readiness(self) -> ReadinessResponse:
        database, redis = await asyncio.gather(
            self._check("database", self._db.ping),
            self._check("redis", self._ping_cache),
        )
        if database.status is CheckStatus.FAIL:
            status = ReadyStatus.UNAVAILABLE
        elif redis.status is CheckStatus.FAIL:
            status = ReadyStatus.DEGRADED
        else:
            status = ReadyStatus.OK
        return ReadinessResponse(status=status, checks={"database": database, "redis": redis})

    async def _ping_cache(self) -> None:
        await self._cache.ping()

    async def _check(self, name: str, probe: Callable[[], Awaitable[None]]) -> DependencyCheck:
        start = time.perf_counter()
        try:
            await asyncio.wait_for(probe(), timeout=self._timeout)
        except Exception as exc:
            logger.warning("readiness_check_failed", extra={"check": name, "error": repr(exc)})
            # Only the exception type goes in the response; details stay in the logs.
            return DependencyCheck(status=CheckStatus.FAIL, error=type(exc).__name__)
        latency = round((time.perf_counter() - start) * 1000, 2)
        return DependencyCheck(status=CheckStatus.OK, latency_ms=latency)
