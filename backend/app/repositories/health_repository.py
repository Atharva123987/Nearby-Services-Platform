from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class HealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> None:
        """Round-trip to Postgres; raises if the database is unreachable."""
        await self._session.execute(text("SELECT 1"))
