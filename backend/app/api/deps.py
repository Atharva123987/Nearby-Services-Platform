"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.repositories.admin_repository import AdminRepository
from app.repositories.health_repository import HealthRepository
from app.repositories.service_repository import ServiceRepository
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
