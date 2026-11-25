import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from app.core.errors import NotFoundError
from app.models.service import ServiceCategory
from app.schemas.service import ServiceCreate, ServiceRead
from app.services.service_service import ServiceService


class FakeRepo:
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

    async def commit(self) -> None:
        self.commits += 1


def test_create_commits_and_get_returns() -> None:
    repo = FakeRepo()
    service = ServiceService(repo)
    data = ServiceCreate(name="ATM", category=ServiceCategory.ATM, latitude=1.0, longitude=2.0)
    created = asyncio.run(service.create(data))
    assert repo.commits == 1
    assert asyncio.run(service.get(created.id)) == created


def test_get_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        asyncio.run(ServiceService(FakeRepo()).get(uuid.uuid4()))
