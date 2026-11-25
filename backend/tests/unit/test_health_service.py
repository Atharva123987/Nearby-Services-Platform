import asyncio

from app.schemas.health import CheckStatus, ReadyStatus
from app.services.health_service import HealthService


class Ok:
    async def ping(self) -> None:
        return None


class Down:
    async def ping(self) -> None:
        raise ConnectionError("refused")


class Hangs:
    async def ping(self) -> None:
        await asyncio.sleep(10)


def readiness(db: object, cache: object, timeout: float = 0.5) -> object:
    service = HealthService(db=db, cache=cache, timeout_seconds=timeout)  # type: ignore[arg-type]
    return asyncio.run(service.readiness())


def test_all_ok() -> None:
    result = readiness(Ok(), Ok())
    assert result.status is ReadyStatus.OK  # type: ignore[attr-defined]


def test_redis_down_is_degraded() -> None:
    result = readiness(Ok(), Down())
    assert result.status is ReadyStatus.DEGRADED  # type: ignore[attr-defined]
    assert result.checks["redis"].error == "ConnectionError"  # type: ignore[attr-defined]


def test_database_down_is_unavailable() -> None:
    result = readiness(Down(), Ok())
    assert result.status is ReadyStatus.UNAVAILABLE  # type: ignore[attr-defined]


def test_hanging_dependency_times_out() -> None:
    result = readiness(Ok(), Hangs(), timeout=0.05)
    assert result.checks["redis"].status is CheckStatus.FAIL  # type: ignore[attr-defined]
    assert result.checks["redis"].error == "TimeoutError"  # type: ignore[attr-defined]
