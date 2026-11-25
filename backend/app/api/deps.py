"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError
from app.models.admin import Admin
from app.repositories.admin_repository import AdminRepository
from app.repositories.health_repository import HealthRepository
from app.repositories.service_repository import ServiceRepository
from app.services.auth_service import AuthService
from app.services.health_service import HealthService
from app.services.service_service import ServiceService

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


def get_service_service(repository: ServiceRepositoryDep) -> ServiceService:
    return ServiceService(repository)


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
