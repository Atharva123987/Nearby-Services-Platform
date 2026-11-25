"""Data access for services. All SQL / PostGIS for the table lives here."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import ColumnElement, cast, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service, ServiceCategory
from app.schemas.service import (
    BBox,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
)
from app.utils.geo import SRID_WGS84, make_point

# geography -> geometry so ST_X/ST_Y can read the point back (X = lng, Y = lat).
_lng = func.ST_X(cast(Service.location, Geometry)).label("lng")
_lat = func.ST_Y(cast(Service.location, Geometry)).label("lat")

# Geography ST_Distance rounds to 10 nanometres, while ST_DWithin compares
# before rounding. Allow that precision so points on the boundary are included.
_NEARBY_RADIUS_TOLERANCE_M = 1e-8


def _to_read(row: Sequence[Any]) -> ServiceRead:
    service, lng, lat = row[:3]
    return ServiceRead(
        id=service.id,
        name=service.name,
        category=service.category,
        latitude=lat,
        longitude=lng,
        rating=service.rating,
        metadata=service.meta,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ServiceCreate) -> ServiceRead:
        service = Service(
            name=data.name,
            category=data.category,
            location=make_point(lat=data.latitude, lng=data.longitude),
            rating=data.rating,
            meta=data.metadata,
        )
        self._session.add(service)
        await self._session.flush()
        created = await self.get(service.id)
        assert created is not None  # noqa: S101 - just inserted in this transaction
        return created

    async def get(self, service_id: uuid.UUID, *, for_update: bool = False) -> ServiceRead | None:
        stmt = select(Service, _lng, _lat).where(Service.id == service_id)
        if for_update:
            stmt = stmt.with_for_update()
        row = (await self._session.execute(stmt)).one_or_none()
        return _to_read(row) if row is not None else None

    async def nearby(
        self,
        *,
        lat: float,
        lng: float,
        radius_m: float,
        limit: int,
        offset: int,
        category: ServiceCategory | None = None,
    ) -> tuple[list[tuple[ServiceRead, float]], int]:
        """(service, distance in metres) within radius_m, nearest first, plus the total."""
        origin = make_point(lat=lat, lng=lng)
        filters: list[ColumnElement[bool]] = [
            func.ST_DWithin(Service.location, origin, radius_m + _NEARBY_RADIUS_TOLERANCE_M)
        ]
        if category is not None:
            filters.append(Service.category == category)

        total = (
            await self._session.execute(select(func.count()).select_from(Service).where(*filters))
        ).scalar_one()
        if offset >= total:
            return [], total

        distance = func.ST_Distance(Service.location, origin).label("distance_m")
        stmt = (
            select(Service, _lng, _lat, distance)
            .where(*filters)
            .order_by(distance, Service.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(_to_read(row), row.distance_m) for row in rows], total

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        category: ServiceCategory | None = None,
        search: str | None = None,
        bbox: BBox | None = None,
    ) -> tuple[list[ServiceRead], int]:
        """One page ordered newest first (id breaks ties so pages don't shift), plus the total."""
        filters = []
        if category is not None:
            filters.append(Service.category == category)
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(Service.name.ilike(f"%{escaped}%", escape="\\"))

        if bbox is not None:
            if bbox.min_lng == bbox.max_lng or bbox.min_lat == bbox.max_lat:
                # PostGIS envelopes with zero area are degenerate polygons.
                filters.extend(
                    (
                        _lng.between(bbox.min_lng, bbox.max_lng),
                        _lat.between(bbox.min_lat, bbox.max_lat),
                    )
                )
            else:
                envelope = func.ST_MakeEnvelope(
                    bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat, SRID_WGS84
                )
                # Planar geometry keeps the box edges on latitude and longitude lines.
                filters.append(func.ST_Intersects(cast(Service.location, Geometry), envelope))

        total = (
            await self._session.execute(select(func.count()).select_from(Service).where(*filters))
        ).scalar_one()
        if offset >= total:
            return [], total

        stmt = (
            select(Service, _lng, _lat)
            .where(*filters)
            .order_by(Service.created_at.desc(), Service.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [_to_read(row) for row in rows], total

    async def update(self, service_id: uuid.UUID, data: ServiceUpdate) -> ServiceRead | None:
        fields = data.model_fields_set
        values: dict[str, Any] = {}
        for field in ("name", "category", "rating"):
            if field in fields:
                values[field] = getattr(data, field)
        if "metadata" in fields:
            values["meta"] = data.metadata
        if data.latitude is not None and data.longitude is not None:
            values["location"] = make_point(lat=data.latitude, lng=data.longitude)
        if values:
            stmt = (
                update(Service)
                .where(Service.id == service_id)
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            await self._session.execute(stmt)
        return await self.get(service_id)

    async def delete(self, service_id: uuid.UUID) -> bool:
        stmt = delete(Service).where(Service.id == service_id).returning(Service.id)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def exists_nearby(
        self,
        name: str,
        lat: float,
        lng: float,
        radius_m: float,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """Check for a duplicate while holding the name lock until the transaction ends."""
        normalized_name = func.lower(name)
        # Serialize checks and writes for this name, including when no matching row exists yet.
        lock_key = func.hashtextextended(func.concat("services:", normalized_name), 0)
        await self._session.execute(select(func.pg_advisory_xact_lock(lock_key)))
        stmt = select(Service.id).where(
            func.lower(Service.name) == normalized_name,
            func.ST_DWithin(Service.location, make_point(lat=lat, lng=lng), radius_m),
        )
        if exclude_id is not None:
            stmt = stmt.where(Service.id != exclude_id)
        return (await self._session.execute(stmt.limit(1))).first() is not None

    async def commit(self) -> None:
        await self._session.commit()
