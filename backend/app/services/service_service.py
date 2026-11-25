"""Business logic for services. Depends on a repository protocol, not on SQLAlchemy."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.core.errors import ConflictError, NotFoundError
from app.models.service import ServiceCategory
from app.schemas.service import BBox, ServiceCreate, ServicePage, ServiceRead, ServiceUpdate

# Same name (case-insensitive) within this many metres counts as a duplicate.
DUPLICATE_RADIUS_M = 10.0


class ServiceRepositoryProtocol(Protocol):
    async def create(self, data: ServiceCreate) -> ServiceRead: ...
    async def get(
        self, service_id: uuid.UUID, *, for_update: bool = False
    ) -> ServiceRead | None: ...
    async def list(
        self,
        *,
        limit: int,
        offset: int,
        category: ServiceCategory | None = None,
        search: str | None = None,
        bbox: BBox | None = None,
    ) -> tuple[list[ServiceRead], int]: ...
    async def update(self, service_id: uuid.UUID, data: ServiceUpdate) -> ServiceRead | None: ...
    async def delete(self, service_id: uuid.UUID) -> bool: ...
    async def exists_nearby(
        self,
        name: str,
        lat: float,
        lng: float,
        radius_m: float,
        exclude_id: uuid.UUID | None = None,
    ) -> bool: ...
    async def commit(self) -> None: ...


class ServiceService:
    def __init__(self, repository: ServiceRepositoryProtocol) -> None:
        self._repo = repository

    async def create(self, data: ServiceCreate) -> ServiceRead:
        await self._ensure_not_duplicate(data.name, data.latitude, data.longitude)
        service = await self._repo.create(data)
        await self._repo.commit()
        return service

    async def get(self, service_id: uuid.UUID, *, for_update: bool = False) -> ServiceRead:
        service = await self._repo.get(service_id, for_update=for_update)
        if service is None:
            raise NotFoundError(f"Service {service_id} not found")
        return service

    async def list(
        self,
        page: int,
        page_size: int,
        category: ServiceCategory | None = None,
        search: str | None = None,
        bbox: BBox | None = None,
    ) -> ServicePage:
        """A page past the end returns empty items (total still reflects all matches)."""
        items, total = await self._repo.list(
            limit=page_size,
            offset=(page - 1) * page_size,
            category=category,
            search=search.strip() if search else None,
            bbox=bbox,
        )
        return ServicePage(items=items, page=page, page_size=page_size, total=total)

    async def update(self, service_id: uuid.UUID, data: ServiceUpdate) -> ServiceRead:
        current = await self.get(service_id, for_update=True)
        if data.name is not None or data.latitude is not None:
            await self._ensure_not_duplicate(
                data.name or current.name,
                data.latitude if data.latitude is not None else current.latitude,
                data.longitude if data.longitude is not None else current.longitude,
                exclude_id=service_id,
            )
        updated = await self._repo.update(service_id, data)
        if updated is None:
            raise NotFoundError(f"Service {service_id} not found")
        await self._repo.commit()
        return updated

    async def delete(self, service_id: uuid.UUID) -> None:
        """Deleting an already-deleted (or unknown) service raises NotFoundError (404)."""
        if not await self._repo.delete(service_id):
            raise NotFoundError(f"Service {service_id} not found")
        await self._repo.commit()

    async def _ensure_not_duplicate(
        self, name: str, lat: float, lng: float, exclude_id: uuid.UUID | None = None
    ) -> None:
        if await self._repo.exists_nearby(name, lat, lng, DUPLICATE_RADIUS_M, exclude_id):
            raise ConflictError(
                f"A service named {name!r} already exists within {DUPLICATE_RADIUS_M:g} m"
            )
