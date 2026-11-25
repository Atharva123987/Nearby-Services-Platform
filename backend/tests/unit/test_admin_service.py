import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from app.core.errors import AppError, ConflictError
from app.core.security import verify_password
from app.models.admin import Admin
from app.services.admin_service import AdminService


class FakeRepo:
    def __init__(self) -> None:
        self.admins: dict[str, Admin] = {}
        self.commits = 0

    async def get_by_email(self, email: str) -> Admin | None:
        return self.admins.get(email)

    async def create(self, email: str, password_hash: str) -> Admin:
        admin = Admin(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.admins[email] = admin
        return admin

    async def commit(self) -> None:
        self.commits += 1


def test_create_admin_normalises_email_and_hashes_password() -> None:
    repo = FakeRepo()
    admin = asyncio.run(AdminService(repo).create_admin("  Admin@Example.COM ", "password123"))
    assert admin.email == "admin@example.com"
    assert admin.password_hash != "password123"
    assert verify_password("password123", admin.password_hash)
    assert repo.commits == 1


def test_create_admin_duplicate_raises_conflict() -> None:
    repo = FakeRepo()
    service = AdminService(repo)
    asyncio.run(service.create_admin("a@example.com", "password123"))
    with pytest.raises(ConflictError):
        asyncio.run(service.create_admin("A@example.com", "password123"))


@pytest.mark.parametrize(
    ("email", "password"), [("not-an-email", "password123"), ("a@b.c", "short")]
)
def test_create_admin_rejects_invalid_input(email: str, password: str) -> None:
    with pytest.raises(AppError):
        asyncio.run(AdminService(FakeRepo()).create_admin(email, password))
