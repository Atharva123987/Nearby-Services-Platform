from enum import StrEnum

from pydantic import BaseModel


class CheckStatus(StrEnum):
    OK = "ok"
    FAIL = "fail"


class ReadyStatus(StrEnum):
    OK = "ok"  # all dependencies healthy
    DEGRADED = "degraded"  # cache down: still serving, without caching
    UNAVAILABLE = "unavailable"  # database down: cannot serve


class LivenessResponse(BaseModel):
    status: str = "ok"


class DependencyCheck(BaseModel):
    status: CheckStatus
    latency_ms: float | None = None
    error: str | None = None


class ReadinessResponse(BaseModel):
    status: ReadyStatus
    checks: dict[str, DependencyCheck]
