"""GET /api/v1/services/nearby end to end: httpx AsyncClient -> app -> real PostGIS + Redis.

Set TEST_DATABASE_URL (migrated PostGIS) and TEST_REDIS_URL to enable. Each test runs in a
rolled-back transaction and FLUSHES the Redis DB, so point TEST_REDIS_URL at a spare DB, e.g.
``TEST_REDIS_URL=redis://localhost:6379/15``. Validation 422s are covered in unit tests.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.main import create_app
from app.repositories.service_repository import ServiceRepository
from app.schemas.service import ServiceCreate

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
REDIS_URL = os.environ.get("TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(
    not (DATABASE_URL and REDIS_URL), reason="TEST_DATABASE_URL / TEST_REDIS_URL not set"
)

SETTINGS = Settings(_env_file=None, jwt_secret="z" * 48, cors_origins="http://localhost:3000")
URL = "/api/v1/services/nearby"


def run_api(test: Callable[[AsyncClient, ServiceRepository], Awaitable[None]]) -> None:
    """Run ``test`` against an empty services table and an empty Redis DB, then roll back."""

    async def run() -> None:
        assert DATABASE_URL and REDIS_URL
        engine = create_async_engine(DATABASE_URL)
        redis = Redis.from_url(REDIS_URL, decode_responses=True)
        await redis.flushdb()
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    session = AsyncSession(bind=conn, join_transaction_mode="rollback_only")
                    await session.execute(text("DELETE FROM services"))  # rolled back afterwards

                    # ASGITransport skips lifespan, so wire app state to the test transaction.
                    app = create_app(SETTINGS)
                    app.state.session_factory = lambda: AsyncSession(
                        bind=conn, join_transaction_mode="rollback_only"
                    )
                    app.state.redis = redis
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        await test(client, ServiceRepository(session))
                finally:
                    await trans.rollback()
        finally:
            await redis.flushdb()
            await redis.aclose()
            await engine.dispose()

    asyncio.run(run())


async def seed(repo: ServiceRepository, *rows: tuple[str, float, float]) -> None:
    for name, lat, lng in rows:
        await repo.create(ServiceCreate(name=name, category="atm", latitude=lat, longitude=lng))


def test_nearby_sorted_by_distance_with_accurate_km() -> None:
    async def body(client: AsyncClient, repo: ServiceRepository) -> None:
        # Due north of (0, 0): 0.01 deg ~ 1.106 km, 0.02 deg ~ 2.211 km.
        await seed(repo, ("Far", 0.02, 0), ("Near", 0.01, 0), ("Out", 0.1, 0))
        response = await client.get(URL, params={"lat": 0, "lng": 0, "radius_km": 5})
        assert response.status_code == 200
        data = response.json()
        assert [i["name"] for i in data["items"]] == ["Near", "Far"]
        assert data["total"] == 2
        assert data["items"][0]["distance_km"] == pytest.approx(1.106, abs=0.005)
        assert data["items"][1]["distance_km"] == pytest.approx(2.211, abs=0.005)

    run_api(body)


def test_nearby_radius_boundary() -> None:
    async def body(client: AsyncClient, repo: ServiceRepository) -> None:
        await seed(repo, ("Edge", 0.0099, 0))  # ~1.095 km away
        inside = await client.get(URL, params={"lat": 0, "lng": 0, "radius_km": 1.1})
        outside = await client.get(URL, params={"lat": 0, "lng": 0, "radius_km": 1.09})
        assert [i["name"] for i in inside.json()["items"]] == ["Edge"]
        assert (outside.json()["items"], outside.json()["total"]) == ([], 0)

    run_api(body)


def test_nearby_lat_lng_are_not_swapped() -> None:
    async def body(client: AsyncClient, repo: ServiceRepository) -> None:
        await seed(repo, ("Delhi", 28.6139, 77.209))
        hit = await client.get(URL, params={"lat": 28.6139, "lng": 77.209, "radius_km": 1})
        swapped = await client.get(URL, params={"lat": 77.209, "lng": 28.6139, "radius_km": 1})
        item = hit.json()["items"][0]
        assert (item["latitude"], item["longitude"]) == (28.6139, 77.209)
        assert item["distance_km"] == pytest.approx(0, abs=0.001)
        assert swapped.json()["total"] == 0

    run_api(body)


def test_nearby_is_cached_and_redis_starts_empty() -> None:
    async def body(client: AsyncClient, repo: ServiceRepository) -> None:
        await seed(repo, ("Near", 0.01, 0))
        params = {"lat": 0, "lng": 0, "radius_km": 5}
        first = await client.get(URL, params=params)
        second = await client.get(URL, params=params)
        assert (first.headers["X-Cache"], second.headers["X-Cache"]) == ("MISS", "HIT")
        assert first.json() == second.json()

    # Run twice: the second run would start with a HIT if Redis were not flushed between tests.
    run_api(body)
    run_api(body)


def test_map_markers_include_the_whole_radius_independent_of_list_pagination() -> None:
    async def body(client: AsyncClient, repo: ServiceRepository) -> None:
        await seed(repo, *((str(i), i / 1000, 0) for i in range(32)))
        query = {"lat": 0, "lng": 0, "radius_km": 4}
        page = (await client.get(URL, params=query)).json()
        assert (len(page["items"]), page["total"]) == (20, 32)
        markers = (await client.get(f"{URL}/markers", params=query)).json()["items"]
        assert [item["name"] for item in markers] == [str(i) for i in range(32)]
        assert "metadata" not in markers[0]
        assert (await client.get(f"{URL}/markers", params=query)).headers["X-Cache"] == "HIT"
        smaller = await client.get(f"{URL}/markers", params={**query, "radius_km": 1})
        assert 0 < len(smaller.json()["items"]) < 20
        other = await client.get(f"{URL}/markers", params={**query, "category": "shop"})
        assert other.json()["items"] == []

    run_api(body)
