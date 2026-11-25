"""Business logic for admin accounts."""

from __future__ import annotations

from typing import Protocol

from app.core.errors import AppError, ConflictError
from app.core.security import hash_password
from app.models.admin import Admin
from app.schemas.admin import normalize_email

MIN_PASSWORD_LENGTH = 8


class AdminRepositoryProtocol(Protocol):
    async def get_by_email(self, email: str) -> Admin | None: ...
    async def create(self, email: str, password_hash: str) -> Admin: ...
    async def commit(self) -> None: ...


class AdminService:
    def __init__(self, repository: AdminRepositoryProtocol) -> None:
        self._repo = repository

    async def create_admin(self, email: str, password: str) -> Admin:
        email = normalize_email(email)
        if "@" not in email:
            raise AppError("A valid email is required")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AppError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        if await self._repo.get_by_email(email) is not None:
            raise ConflictError(f"Admin {email} already exists")
        admin = await self._repo.create(email, hash_password(password))
        await self._repo.commit()
        return admin
