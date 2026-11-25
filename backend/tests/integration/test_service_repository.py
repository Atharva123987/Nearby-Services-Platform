"""Runs against a real, migrated PostGIS database.

Set TEST_DATABASE_URL (asyncpg URL) to enable, e.g.
``TEST_DATABASE_URL=postgresql+asyncpg://fieldguide:fieldguide@localhost:5432/fieldguide``.
Tests use rolled-back transactions unless they verify writes across transactions.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import ConflictError
from app.models.service import Service, ServiceCategory
from app.repositories.service_repository import ServiceRepository
from app.schemas.service import BBox, ServiceCreate, ServiceUpdate
from app.services.service_service import ServiceService

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL not set")


def in_rollback(test: Callable[[AsyncSession], Awaitable[None]]) -> None:
    async def run() -> None:
        assert DATABASE_URL is not None
        engine = create_async_engine(DATABASE_URL)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    await test(AsyncSession(bind=conn, join_transaction_mode="rollback_only"))
                finally:
                    await trans.rollback()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_location_stored_as_lng_lat() -> None:
    async def body(session: AsyncSession) -> None:
        repo = ServiceRepository(session)
        created = await repo.create(
            ServiceCreate(name="Delhi ATM", category="ATMs", latitude=28.6139, longitude=77.209)
        )
        assert (created.latitude, created.longitude) == (28.6139, 77.209)
        x, y = (
            await session.execute(
                text(
                    "SELECT ST_X(location::geometry), ST_Y(location::geometry) FROM services WHERE id = :id"
                ),
                {"id": created.id},
            )
        ).one()
        assert (x, y) == (77.209, 28.6139)  # X = longitude, Y = latitude

    in_rollback(body)


def test_distance_is_in_metres() -> None:
    async def body(session: AsyncSession) -> None:
        # One degree of latitude is ~111 km; geometry would report 1.0 (degrees).
        metres = (
            await session.execute(
                text(
                    "SELECT ST_Distance('SRID=4326;POINT(0 0)'::geography,"
                    " 'SRID=4326;POINT(0 1)'::geography)"
                )
            )
        ).scalar_one()
        assert 110_000 < metres < 112_000

    in_rollback(body)


def test_gist_index_used_for_radius_search() -> None:
    async def body(session: AsyncSession) -> None:
        await session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(
            row[0]
            for row in await session.execute(
                text(
                    "EXPLAIN SELECT id FROM services WHERE ST_DWithin(location,"
                    " 'SRID=4326;POINT(77.2 28.6)'::geography, 5000)"
                )
            )
        )
        assert "ix_services_location" in plan

    in_rollback(body)


def test_update_delete_and_nearby_duplicate() -> None:
    async def body(session: AsyncSession) -> None:
        repo = ServiceRepository(session)
        created = await repo.create(
            ServiceCreate(name="Corner ATM", category="atm", latitude=28.6, longitude=77.2)
        )
        # ~5 m north is a duplicate, ~50 m is not; the service itself can be excluded.
        assert await repo.exists_nearby("corner atm", 28.60004, 77.2, 10)
        assert not await repo.exists_nearby("corner atm", 28.6005, 77.2, 10)
        assert not await repo.exists_nearby("Corner ATM", 28.6, 77.2, 10, exclude_id=created.id)

        updated = await repo.update(
            created.id, ServiceUpdate(latitude=10, longitude=20, rating=None)
        )
        assert updated is not None
        assert (updated.latitude, updated.longitude, updated.name) == (10, 20, "Corner ATM")

        assert await repo.delete(created.id)
        assert not await repo.delete(created.id)
        assert await repo.update(created.id, ServiceUpdate(name="x")) is None

    in_rollback(body)


def test_concurrent_creates_reject_duplicate() -> None:
    async def run() -> None:
        assert DATABASE_URL is not None
        engine = create_async_engine(DATABASE_URL)
        sessions = async_sessionmaker(engine)
        name = f"Concurrent ATM {uuid.uuid4()}"

        async def create(candidate: str) -> bool:
            async with sessions() as session:
                service = ServiceService(ServiceRepository(session))
                data = ServiceCreate(name=candidate, category="atm", latitude=28.6, longitude=77.2)
                try:
                    await service.create(data)
                except ConflictError:
                    return False
                return True

        try:
            async with asyncio.TaskGroup() as group:
                first = group.create_task(create(name))
                second = group.create_task(create(name.upper()))
            assert sorted([first.result(), second.result()]) == [False, True]
        finally:
            try:
                async with sessions.begin() as session:
                    await session.execute(
                        delete(Service).where(func.lower(Service.name) == name.lower())
                    )
            finally:
                await engine.dispose()

    asyncio.run(run())


def test_list_filters_searches_and_orders_stably() -> None:
    async def body(session: AsyncSession) -> None:
        await session.execute(text("DELETE FROM services"))  # rolled back afterwards
        repo = ServiceRepository(session)
        # Same transaction => same now() => identical created_at; id must break the tie.
        for i in range(3):
            await repo.create(
                ServiceCreate(name=f"ATM {i}", category="atm", latitude=i, longitude=0)
            )
        await repo.create(ServiceCreate(name="100% Shop", category="shop", latitude=5, longitude=0))

        items, total = await repo.list(limit=2, offset=0, category=ServiceCategory.ATM)
        rest, _ = await repo.list(limit=2, offset=2, category=ServiceCategory.ATM)
        assert total == 3
        ids = [s.id for s in items + rest]
        assert len(set(ids)) == 3 and ids == sorted(ids, reverse=True)

        found, total = await repo.list(limit=10, offset=0, search="0%")
        assert total == 1 and found[0].name == "100% Shop"  # % is matched literally
        assert (await repo.list(limit=10, offset=100))[0] == []
        assert await repo.list(limit=10, offset=2**63) == ([], 4)

    in_rollback(body)


def test_list_bbox_returns_only_services_inside() -> None:
    async def body(session: AsyncSession) -> None:
        await session.execute(text("DELETE FROM services"))  # rolled back afterwards
        repo = ServiceRepository(session)
        for name, lat, lng in [("In", 28.6, 77.2), ("Edge", 28.0, 77.0), ("Out", 28.6, 79.0)]:
            await repo.create(ServiceCreate(name=name, category="atm", latitude=lat, longitude=lng))
        bbox = BBox(min_lng=77, min_lat=28, max_lng=78, max_lat=29)
        items, total = await repo.list(limit=10, offset=0, bbox=bbox)
        assert total == 2 and {s.name for s in items} == {"In", "Edge"}

        point = BBox(min_lng=77.2, min_lat=28.6, max_lng=77.2, max_lat=28.6)
        items, total = await repo.list(limit=10, offset=0, bbox=point)
        assert total == 1 and [s.name for s in items] == ["In"]

    in_rollback(body)
