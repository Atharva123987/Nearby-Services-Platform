"""Business logic for services. Depends on a repository protocol, not on SQLAlchemy."""

from __future__ import annotations

import math
import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

from redis.asyncio import Redis

from app.core.cache import get_or_set, get_version, invalidate
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.service import ServiceCategory
from app.schemas.service import (
    BBox,
    NearbyPage,
    NearbyQuery,
    NearbyServiceRead,
    ServiceCreate,
    ServicePage,
    ServiceRead,
    ServiceUpdate,
)

# List/nearby keys live under services:v{N}; any write INCRs this key, orphaning old entries
# (they expire by TTL). Detail keys are deleted directly instead.
VERSION_KEY = "services:version"

# Same name (case-insensitive) within this many metres counts as a duplicate.
DUPLICATE_RADIUS_M = 10.0


class ServiceRepositoryProtocol(Protocol):
    async def create(self, data: ServiceCreate) -> ServiceRead: ...
    async def get(
        self, service_id: uuid.UUID, *, for_update: bool = False
    ) -> ServiceRead | None: ...
    async def nearby(
        self,
        *,
        lat: float,
        lng: float,
        radius_m: float,
        limit: int,
        offset: int,
        category: ServiceCategory | None = None,
    ) -> tuple[list[tuple[ServiceRead, float]], int]: ...
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
    def __init__(
        self,
        repository: ServiceRepositoryProtocol,
        *,
        cache: Redis | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repo = repository
        self._cache = cache
        self._settings = settings

    async def create(self, data: ServiceCreate) -> ServiceRead:
        await self._ensure_not_duplicate(data.name, data.latitude, data.longitude)
        service = await self._repo.create(data)
        await self._repo.commit()
        await self._invalidate()
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

    async def cached_get(self, service_id: uuid.UUID) -> tuple[ServiceRead, bool]:
        """Public detail read. Returns ``(service, cache_hit)``. Not-found is not cached."""

        async def load() -> dict:
            return (await self.get(service_id)).model_dump(mode="json")

        data, hit = await self._cached(
            _detail_key(service_id),
            load,
            ttl=self._settings.cache_ttl_service_detail_seconds if self._settings else 0,
        )
        return ServiceRead.model_validate(data), hit

    async def cached_list(
        self,
        page: int,
        page_size: int,
        category: ServiceCategory | None = None,
        bbox: BBox | None = None,
    ) -> tuple[ServicePage, bool]:
        """Public list read (admin list uses ``list`` and is never cached)."""
        bbox_key = bbox.model_dump_json() if bbox else None
        key = f"{await self._prefix()}:list:{page}:{page_size}:{category}:{bbox_key}"

        async def load() -> dict:
            result = await self.list(page, page_size, category=category, bbox=bbox)
            return result.model_dump(mode="json")

        data, hit = await self._cached(
            key, load, ttl=self._settings.cache_ttl_default_seconds if self._settings else 0
        )
        return ServicePage.model_validate(data), hit

    async def nearby(self, query: NearbyQuery) -> tuple[NearbyPage, bool]:
        """Return ``(page, cache_hit)``.

        lat/lng are rounded to 3 decimals (~110 m) and the radius up to the next 0.5 km,
        so nearby users share cache entries.
        """
        query = query.model_copy(
            update={
                "lat": round(query.lat, 3),
                "lng": round(query.lng, 3),
                "radius_km": math.ceil(query.radius_km * 2) / 2,
            }
        )
        key = (
            f"{await self._prefix()}:nearby:{query.lat}:{query.lng}:{query.radius_km}"
            f":{query.category}:{query.limit}:{query.offset}"
        )

        async def load() -> dict:
            return (await self._nearby_from_db(query)).model_dump(mode="json")

        data, hit = await self._cached(
            key, load, ttl=self._settings.cache_ttl_search_seconds if self._settings else 0
        )
        return NearbyPage.model_validate(data), hit

    async def _cached(
        self, key: str, load: Callable[[], Awaitable[dict]], *, ttl: int
    ) -> tuple[dict, bool]:
        """Cache-aside over ``load``; results with no ``items`` get the short empty TTL."""
        if self._cache is None or self._settings is None:
            return await load(), False
        return await get_or_set(
            self._cache,
            key,
            load,
            ttl=ttl,
            empty_ttl=self._settings.cache_ttl_empty_seconds,
            is_empty=lambda v: "items" in v and not v["items"],
        )

    async def _nearby_from_db(self, query: NearbyQuery) -> NearbyPage:
        rows, total = await self._repo.nearby(
            lat=query.lat,
            lng=query.lng,
            radius_m=query.radius_km * 1000,
            limit=query.limit,
            offset=query.offset,
            category=query.category,
        )
        items = [
            NearbyServiceRead(**s.model_dump(), distance_km=round(distance_m / 1000, 2))
            for s, distance_m in rows
        ]
        return NearbyPage(items=items, total=total, query=query)

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
        await self._invalidate(service_id)
        return updated

    async def delete(self, service_id: uuid.UUID) -> None:
        """Deleting an already-deleted (or unknown) service raises NotFoundError (404)."""
        if not await self._repo.delete(service_id):
            raise NotFoundError(f"Service {service_id} not found")
        await self._repo.commit()
        await self._invalidate(service_id)

    async def _prefix(self) -> str:
        version = await get_version(self._cache, VERSION_KEY) if self._cache else 0
        return f"services:v{version}"

    async def _invalidate(self, *service_ids: uuid.UUID) -> None:
        """Call once per write (bulk uploads too), only after the commit succeeds."""
        if self._cache is not None:
            await invalidate(self._cache, VERSION_KEY, *(_detail_key(i) for i in service_ids))

    async def _ensure_not_duplicate(
        self, name: str, lat: float, lng: float, exclude_id: uuid.UUID | None = None
    ) -> None:
        if await self._repo.exists_nearby(name, lat, lng, DUPLICATE_RADIUS_M, exclude_id):
            raise ConflictError(
                f"A service named {name!r} already exists within {DUPLICATE_RADIUS_M:g} m"
            )


def _detail_key(service_id: uuid.UUID) -> str:
    return f"service:{service_id}"
