"""Data access for services. All SQL / PostGIS for the table lives here."""

from __future__ import annotations

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Row, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceRead
from app.utils.geo import make_point

# geography -> geometry so ST_X/ST_Y can read the point back (X = lng, Y = lat).
_lng = func.ST_X(cast(Service.location, Geometry)).label("lng")
_lat = func.ST_Y(cast(Service.location, Geometry)).label("lat")


def _to_read(row: Row[Service, float, float]) -> ServiceRead:
    service, lng, lat = row
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

    async def get(self, service_id: uuid.UUID) -> ServiceRead | None:
        stmt = select(Service, _lng, _lat).where(Service.id == service_id)
        row = (await self._session.execute(stmt)).one_or_none()
        return _to_read(row) if row is not None else None

    async def commit(self) -> None:
        await self._session.commit()
