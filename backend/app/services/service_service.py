"""Business logic for services. Depends on a repository protocol, not on SQLAlchemy."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

from app.core.cache import get_or_set, get_version, invalidate
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.service import ServiceCategory
from app.schemas.service import (
    BBox,
    BulkRowError,
    BulkUploadResult,
    MarkerArea,
    NearbyMarker,
    NearbyMarkers,
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
    async def bulk_create(self, items: Sequence[ServiceCreate]) -> None: ...
    async def get(
        self, service_id: uuid.UUID, *, for_update: bool = False
    ) -> ServiceRead | None: ...
    async def nearby_markers(self, area: MarkerArea) -> list[NearbyMarker]: ...
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

    async def bulk_create(
        self, rows: list[dict[str, Any]], mode: Literal["partial", "strict"] = "partial"
    ) -> BulkUploadResult:
        """Validate every row; partial inserts the valid ones, strict inserts nothing on any error.

        Rows that repeat an earlier row in the file (same name, case-insensitive, and same
        coordinates) are reported as errors. Existing services are not checked for duplicates.
        """
        valid: list[ServiceCreate] = []
        errors: list[BulkRowError] = []
        seen: dict[tuple[str, float, float], int] = {}
        for number, raw in enumerate(rows, start=1):
            data, row_errors = _validate_row(number, raw)
            if data is not None:
                key = (data.name.casefold(), data.latitude, data.longitude)
                if key in seen:
                    row_errors.append(
                        BulkRowError(
                            row=number, field=None, message=f"duplicate of row {seen[key]}"
                        )
                    )
                else:
                    seen[key] = number
                    valid.append(data)
            errors.extend(row_errors)

        failed = len({e.row for e in errors})
        if valid and not (mode == "strict" and errors):
            await self._repo.bulk_create(valid)
            await self._repo.commit()
            await self._invalidate()
            inserted = len(valid)
        else:
            inserted = 0
        return BulkUploadResult(total=len(rows), inserted=inserted, failed=failed, errors=errors)

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

        return await self._cached(
            _detail_key(service_id),
            lambda: self.get(service_id),
            model=ServiceRead,
            version_key=VERSION_KEY,
            ttl=self._settings.cache_ttl_service_detail_seconds if self._settings else 0,
        )

    async def cached_list(
        self,
        page: int,
        page_size: int,
        category: ServiceCategory | None = None,
        bbox: BBox | None = None,
    ) -> tuple[ServicePage, bool]:
        """Public list read (admin list uses ``list`` and is never cached)."""
        bbox_key = bbox.model_dump_json() if bbox else None
        ttl = self._settings.cache_ttl_default_seconds if self._settings else 0
        prefix = await self._prefix() if ttl else None
        key = f"{prefix}:list:{page}:{page_size}:{category}:{bbox_key}" if prefix else None
        return await self._cached(
            key,
            lambda: self.list(page, page_size, category=category, bbox=bbox),
            model=ServicePage,
            ttl=ttl,
        )

    async def nearby(self, query: NearbyQuery) -> tuple[NearbyPage, bool]:
        """Return ``(page, cache_hit)`` for the exact centre and radius."""
        ttl = self._settings.cache_ttl_search_seconds if self._settings else 0
        prefix = await self._prefix() if ttl else None
        key = None
        if prefix:
            key = (
                f"{prefix}:nearby:exact:{query.lat}:{query.lng}:{float(query.radius_km)}"
                f":{query.category}:{query.limit}:{query.offset}"
            )
        return await self._cached(
            key, lambda: self._nearby_from_db(query), model=NearbyPage, ttl=ttl
        )

    async def nearby_markers(self, area: MarkerArea) -> tuple[NearbyMarkers, bool]:
        ttl = self._settings.cache_ttl_search_seconds if self._settings else 0
        prefix = await self._prefix() if ttl else None
        key = (
            f"{prefix}:markers:{area.lat}:{area.lng}:{area.radius_km}:{area.category}"
            if prefix
            else None
        )

        async def load() -> NearbyMarkers:
            return NearbyMarkers(items=await self._repo.nearby_markers(area))

        return await self._cached(key, load, model=NearbyMarkers, ttl=ttl)

    async def _cached[ReadModel: BaseModel](
        self,
        key: str | None,
        load: Callable[[], Awaitable[ReadModel]],
        *,
        model: type[ReadModel],
        ttl: int,
        version_key: str | None = None,
    ) -> tuple[ReadModel, bool]:
        """Cache-aside over ``load``; results with no ``items`` get the short empty TTL."""
        if key is None or self._cache is None or self._settings is None or ttl == 0:
            return await load(), False

        async def load_json() -> dict[str, object]:
            return (await load()).model_dump(mode="json")

        data, hit = await get_or_set(
            self._cache,
            key,
            load_json,
            ttl=ttl,
            empty_ttl=self._settings.cache_ttl_empty_seconds,
            is_empty=lambda v: "items" in v and not v["items"],
            validate=model.model_validate,
            version_key=version_key,
        )
        return model.model_validate(data), hit

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

    async def _prefix(self) -> str | None:
        version = await get_version(self._cache, VERSION_KEY) if self._cache else None
        return f"services:v{version}" if version is not None else None

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


def _validate_row(
    number: int, raw: dict[str, Any]
) -> tuple[ServiceCreate | None, list[BulkRowError]]:
    values = dict(raw)
    for field in ("rating", "metadata"):
        if values.get(field) == "":  # empty CSV cell
            values[field] = None
    if isinstance(values.get("metadata"), str):  # CSV carries metadata as a JSON string
        try:
            values["metadata"] = json.loads(values["metadata"])
        except json.JSONDecodeError:
            return None, [BulkRowError(row=number, field="metadata", message="invalid JSON")]
    try:
        return ServiceCreate.model_validate(values), []
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc: str | None = str(err["loc"][0]) if err["loc"] else None
            message = err["msg"]
            if loc == "latitude" and _looks_swapped(values):
                message += " (latitude and longitude may be swapped)"
            errors.append(BulkRowError(row=number, field=loc, message=message))
        return None, errors


def _looks_swapped(values: dict[str, Any]) -> bool:
    try:
        lat, lng = float(values["latitude"]), float(values["longitude"])
    except (KeyError, TypeError, ValueError):
        return False
    return abs(lat) > 90 and abs(lat) <= 180 and abs(lng) <= 90


def _detail_key(service_id: uuid.UUID) -> str:
    return f"service:{service_id}"
