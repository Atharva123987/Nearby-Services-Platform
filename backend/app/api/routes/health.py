from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_health_service
from app.schemas.health import LivenessResponse, ReadinessResponse, ReadyStatus
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=LivenessResponse)
async def health() -> LivenessResponse:
    """Liveness: 200 while the process serves HTTP. Touches no dependencies."""
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Database unavailable"}},
)
async def ready(
    response: Response, service: Annotated[HealthService, Depends(get_health_service)]
) -> ReadinessResponse:
    """Readiness: 200 when the database is up (Redis down => "degraded"), else 503."""
    result = await service.readiness()
    if result.status is ReadyStatus.UNAVAILABLE:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
