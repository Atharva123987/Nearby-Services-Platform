"""Runs against a real, migrated PostGIS database.

Set TEST_DATABASE_URL (asyncpg URL) to enable, e.g.
``TEST_DATABASE_URL=postgresql+asyncpg://fieldguide:fieldguide@localhost:5432/fieldguide``.
Each test runs inside a transaction that is rolled back.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.repositories.service_repository import ServiceRepository
from app.schemas.service import ServiceCreate

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
