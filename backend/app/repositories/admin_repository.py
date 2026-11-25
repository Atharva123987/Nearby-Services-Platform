"""Data access for admin accounts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> Admin | None:
        """``email`` must already be normalised (lower-cased, trimmed)."""
        result = await self._session.execute(select(Admin).where(Admin.email == email))
        return result.scalar_one_or_none()

    async def create(self, email: str, password_hash: str) -> Admin:
        admin = Admin(email=email, password_hash=password_hash)
        self._session.add(admin)
        await self._session.flush()
        await self._session.refresh(admin)
        return admin

    async def commit(self) -> None:
        await self._session.commit()
