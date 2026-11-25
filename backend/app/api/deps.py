"""Shared FastAPI dependencies."""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import rate_limit
from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError
from app.models.admin import Admin
from app.repositories.admin_repository import AdminRepository
from app.repositories.health_repository import HealthRepository
from app.repositories.service_repository import ServiceRepository
from app.services.auth_service import AuthService
from app.services.health_service import HealthService
from app.services.service_service import ServiceService

logger = logging.getLogger(__name__)

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def get_health_service(
    session: DbSessionDep, redis: RedisDep, settings: SettingsDep
) -> HealthService:
    return HealthService(
        db=HealthRepository(session),
        cache=redis,
        timeout_seconds=settings.ready_check_timeout_seconds,
    )


def get_service_repository(session: DbSessionDep) -> ServiceRepository:
    return ServiceRepository(session)


def get_admin_repository(session: DbSessionDep) -> AdminRepository:
    return AdminRepository(session)


ServiceRepositoryDep = Annotated[ServiceRepository, Depends(get_service_repository)]
AdminRepositoryDep = Annotated[AdminRepository, Depends(get_admin_repository)]


def get_service_service(
    repository: ServiceRepositoryDep, redis: RedisDep, settings: SettingsDep
) -> ServiceService:
    return ServiceService(repository, cache=redis, settings=settings)


ServiceServiceDep = Annotated[ServiceService, Depends(get_service_service)]


def get_auth_service(repository: AdminRepositoryDep, settings: SettingsDep) -> AuthService:
    return AuthService(repository, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# auto_error=False: a missing/garbled header becomes our 401 envelope, not FastAPI's 403.
# Also gives Swagger its "Authorize" button (paste the access token).
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    service: AuthServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Admin:
    if credentials is None:
        raise InvalidTokenError("Not authenticated")
    return await service.get_current_admin(credentials.credentials)


CurrentAdminDep = Annotated[Admin, Depends(get_current_admin)]


def rate_limiter(
    scope: str, limit_setting: str, *, fail_open: bool
) -> Callable[[Request, Response, SettingsDep], Awaitable[None]]:
    """Per-IP limit of ``settings.<limit_setting>`` requests per minute (see core/rate_limit).

    Sets ``X-RateLimit-Limit/Remaining/Reset`` (reset = Unix time the window ends). When
    several tiers apply to a route, the route's own (stricter) tier sets them last.
    """

    async def dependency(request: Request, response: Response, settings: SettingsDep) -> None:
        if not settings.rate_limit_enabled:
            return
        redis = request.app.state.redis
        ip = rate_limit.client_ip(
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
            settings.trusted_proxies,
        )
        limit: int = getattr(settings, limit_setting)
        try:
            count, reset_at = await rate_limit.hit(redis, f"{scope}:{ip}")
        except RedisError as exc:
            logger.warning("rate limit check failed", extra={"scope": scope, "error": str(exc)})
            if fail_open:
                return
            raise HTTPException(503, "Service temporarily unavailable") from exc
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(limit - count, 0)),
            "X-RateLimit-Reset": str(reset_at),
        }
        if count > limit:
            retry_after = max(reset_at - int(time.time()), 1)
            raise HTTPException(
                429, "Rate limit exceeded", headers={**headers, "Retry-After": str(retry_after)}
            )
        response.headers.update(headers)

    return dependency


# Public routes stay up if Redis is down; login does not (no brute force during an outage).
default_rate_limit = rate_limiter("default", "rate_limit_default_per_minute", fail_open=True)
auth_rate_limit = rate_limiter("auth", "rate_limit_auth_per_minute", fail_open=False)
nearby_rate_limit = rate_limiter("nearby", "rate_limit_nearby_per_minute", fail_open=True)
admin_write_rate_limit = rate_limiter(
    "admin_write", "rate_limit_admin_write_per_minute", fail_open=True
)
