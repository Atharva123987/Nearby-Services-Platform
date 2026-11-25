import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.models.service import ServiceCategory
from app.schemas.service import BBox, ServiceCreate, ServiceRead, ServiceUpdate
from app.services.service_service import ServiceService


class FakeRepo:
    """In-memory repo. "Nearby" means identical coordinates, which is enough for these tests."""

    def __init__(self) -> None:
        self.items: dict[uuid.UUID, ServiceRead] = {}
        self.commits = 0

    async def create(self, data: ServiceCreate) -> ServiceRead:
        now = datetime.now(UTC)
        item = ServiceRead(
            id=uuid.uuid4(),
            name=data.name,
            category=data.category,
            latitude=data.latitude,
            longitude=data.longitude,
            rating=data.rating,
            metadata=data.metadata,
            created_at=now,
            updated_at=now,
        )
        self.items[item.id] = item
        return item

    async def get(self, service_id: uuid.UUID) -> ServiceRead | None:
        return self.items.get(service_id)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        category: ServiceCategory | None = None,
        search: str | None = None,
        bbox: BBox | None = None,
    ) -> tuple[list[ServiceRead], int]:
        matches = [
            s
            for s in self.items.values()
            if (category is None or s.category == category)
            and (not search or search.lower() in s.name.lower())
            and (
                bbox is None
                or (
                    bbox.min_lng <= s.longitude <= bbox.max_lng
                    and bbox.min_lat <= s.latitude <= bbox.max_lat
                )
            )
        ]
        matches.sort(key=lambda s: (s.created_at, s.id), reverse=True)
        return matches[offset : offset + limit], len(matches)

    async def update(self, service_id: uuid.UUID, data: ServiceUpdate) -> ServiceRead | None:
        if service_id not in self.items:
            return None
        item = self.items[service_id].model_copy(update=data.model_dump(exclude_unset=True))
        self.items[service_id] = item
        return item

    async def delete(self, service_id: uuid.UUID) -> bool:
        return self.items.pop(service_id, None) is not None

    async def exists_nearby(
        self,
        name: str,
        lat: float,
        lng: float,
        radius_m: float,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        return any(
            s.id != exclude_id
            and s.name.lower() == name.lower()
            and (s.latitude, s.longitude) == (lat, lng)
            for s in self.items.values()
        )

    async def commit(self) -> None:
        self.commits += 1


def make(name: str = "ATM", lat: float = 1.0, lng: float = 2.0) -> ServiceCreate:
    return ServiceCreate(name=name, category=ServiceCategory.ATM, latitude=lat, longitude=lng)


def test_create_commits_and_get_returns() -> None:
    repo = FakeRepo()
    service = ServiceService(repo)
    created = asyncio.run(service.create(make()))
    assert repo.commits == 1
    assert asyncio.run(service.get(created.id)) == created


def test_get_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        asyncio.run(ServiceService(FakeRepo()).get(uuid.uuid4()))


def test_create_duplicate_raises_conflict() -> None:
    service = ServiceService(FakeRepo())
    asyncio.run(service.create(make("Corner ATM")))
    with pytest.raises(ConflictError):
        asyncio.run(service.create(make("corner atm")))
    asyncio.run(service.create(make("Corner ATM", lat=5.0)))  # elsewhere is fine


def test_update_changes_only_sent_fields() -> None:
    repo = FakeRepo()
    service = ServiceService(repo)
    created = asyncio.run(service.create(make()))
    updated = asyncio.run(service.update(created.id, ServiceUpdate(name="New name")))
    assert updated.name == "New name"
    assert (updated.latitude, updated.longitude) == (1.0, 2.0)
    assert repo.commits == 2


def test_update_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        asyncio.run(ServiceService(FakeRepo()).update(uuid.uuid4(), ServiceUpdate(name="x")))


def test_update_into_duplicate_raises_conflict() -> None:
    service = ServiceService(FakeRepo())
    asyncio.run(service.create(make("A")))
    other = asyncio.run(service.create(make("B")))
    with pytest.raises(ConflictError):
        asyncio.run(service.update(other.id, ServiceUpdate(name="A")))


def test_update_same_name_on_itself_is_not_a_duplicate() -> None:
    service = ServiceService(FakeRepo())
    created = asyncio.run(service.create(make("A")))
    asyncio.run(service.update(created.id, ServiceUpdate(name="A")))


def test_delete_then_second_delete_is_not_found() -> None:
    service = ServiceService(FakeRepo())
    created = asyncio.run(service.create(make()))
    asyncio.run(service.delete(created.id))
    with pytest.raises(NotFoundError):
        asyncio.run(service.delete(created.id))


def test_list_paginates_and_reports_total() -> None:
    service = ServiceService(FakeRepo())
    for i in range(5):
        asyncio.run(service.create(make(f"ATM {i}", lat=float(i))))
    page = asyncio.run(service.list(page=2, page_size=2))
    assert (len(page.items), page.page, page.page_size, page.total) == (2, 2, 2, 5)
    beyond = asyncio.run(service.list(page=10, page_size=2))
    assert (beyond.items, beyond.total) == ([], 5)
