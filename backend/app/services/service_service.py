"""Business logic for services. Depends on a repository protocol, not on SQLAlchemy."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.core.errors import NotFoundError
from app.schemas.service import ServiceCreate, ServiceRead


class ServiceRepositoryProtocol(Protocol):
    async def create(self, data: ServiceCreate) -> ServiceRead: ...
    async def get(self, service_id: uuid.UUID) -> ServiceRead | None: ...
    async def commit(self) -> None: ...


class ServiceService:
    def __init__(self, repository: ServiceRepositoryProtocol) -> None:
        self._repo = repository

    async def create(self, data: ServiceCreate) -> ServiceRead:
        service = await self._repo.create(data)
        await self._repo.commit()
        return service

    async def get(self, service_id: uuid.UUID) -> ServiceRead:
        service = await self._repo.get(service_id)
        if service is None:
            raise NotFoundError(f"Service {service_id} not found")
        return service
