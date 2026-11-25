"""Shared FastAPI dependencies."""

import hashlib
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
from app.schemas.admin import normalize_email
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


def _client_ip(request: Request, settings: Settings) -> str:
    return rate_limit.client_ip(
        request.client.host if request.client else None,
        request.headers.get("x-forwarded-for"),
        settings.trusted_proxies,
    )


async def enforce_rate_limit(
    request: Request,
    response: Response,
    settings: Settings,
    key: str,
    limit: int,
    *,
    window_seconds: int = rate_limit.WINDOW_SECONDS,
    fail_open: bool,
) -> None:
    """Count one request against ``key``; 429 once ``limit`` is exceeded in the window.

    Sets ``X-RateLimit-Limit/Remaining/Reset`` (reset = Unix time the window ends). When
    several limits apply to a request, the last one checked sets them.
    """
    if not settings.rate_limit_enabled:
        return
    try:
        count, reset_at = await rate_limit.hit(request.app.state.redis, key, window_seconds)
    except RedisError as exc:
        logger.warning("rate limit check failed", extra={"key": key, "error": str(exc)})
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


def rate_limiter(
    scope: str, limit_setting: str, *, fail_open: bool
) -> Callable[[Request, Response, SettingsDep], Awaitable[None]]:
    """Per-IP limit of ``settings.<limit_setting>`` requests per minute."""

    async def dependency(request: Request, response: Response, settings: SettingsDep) -> None:
        key = f"{scope}:{_client_ip(request, settings)}"
        limit: int = getattr(settings, limit_setting)
        await enforce_rate_limit(request, response, settings, key, limit, fail_open=fail_open)

    return dependency


# Public routes stay up if Redis is down.
default_rate_limit = rate_limiter("default", "rate_limit_default_per_minute", fail_open=True)
nearby_rate_limit = rate_limiter("nearby", "rate_limit_nearby_per_minute", fail_open=True)
admin_write_rate_limit = rate_limiter(
    "admin_write", "rate_limit_admin_write_per_minute", fail_open=True
)

_LOGIN_WINDOWS = ((60, "rate_limit_login_per_minute"), (3600, "rate_limit_login_per_hour"))


def _login_email_key(email: str) -> str:
    # Hashed so Redis keys don't hold email addresses.
    return "login:email:" + hashlib.sha256(normalize_email(email).encode()).hexdigest()


async def enforce_login_rate_limit(
    request: Request, response: Response, settings: Settings, email: str
) -> None:
    """Per-IP and per-email login limits. Fails closed: no brute force while Redis is down."""
    for key in (f"login:ip:{_client_ip(request, settings)}", _login_email_key(email)):
        for window_seconds, limit_setting in _LOGIN_WINDOWS:
            await enforce_rate_limit(
                request,
                response,
                settings,
                key,
                getattr(settings, limit_setting),
                window_seconds=window_seconds,
                fail_open=False,
            )


async def reset_login_email_rate_limit(request: Request, settings: Settings, email: str) -> None:
    """Called after a successful login. Per-IP counters are kept, so logging in to one
    valid account does not reset an attacker's IP budget."""
    if not settings.rate_limit_enabled:
        return
    key = _login_email_key(email)
    try:
        for window_seconds, _ in _LOGIN_WINDOWS:
            await rate_limit.reset(request.app.state.redis, key, window_seconds)
    except RedisError as exc:
        logger.warning("login rate limit reset failed", extra={"error": str(exc)})
