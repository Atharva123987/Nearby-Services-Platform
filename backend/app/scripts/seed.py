"""Replace every service with the sample dataset (dev only).

Usage::

    python -m app.scripts.seed [/data/sample_services.csv]

Accepts the same .csv / .json files as the bulk upload endpoint and loads them in strict mode,
so a bad row aborts the seed. Existing services are deleted first, so it is safe to re-run.
Refuses to run with APP_ENV=prod.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import delete

from app.cache.redis import create_redis
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory
from app.models.service import Service
from app.repositories.service_repository import ServiceRepository
from app.services.bulk_upload import file_format, parse_upload
from app.services.service_service import ServiceService

logger = logging.getLogger("app.scripts.seed")


async def _seed(rows: list[dict[str, Any]], path: Path) -> int:
    settings = get_settings()
    engine = create_engine(settings)
    redis = create_redis(settings)  # bulk_create bumps the cache version after commit
    try:
        async with create_session_factory(engine)() as session:
            await session.execute(delete(Service))  # committed together with the insert
            service = ServiceService(ServiceRepository(session), cache=redis, settings=settings)
            result = await service.bulk_create(rows, "strict")
        if result.errors:
            for error in result.errors[:20]:
                logger.error("Invalid row", extra=error.model_dump())
            return 1
        logger.info("Seeded services", extra={"inserted": result.inserted, "file": str(path)})
        return 0
    finally:
        await redis.aclose()
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replace all services with a sample dataset.")
    parser.add_argument("file", nargs="?", default="/data/sample_services.csv", type=Path)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level.value)
    if settings.is_prod:
        logger.error("Refusing to seed with APP_ENV=prod")
        return 1
    try:
        rows = parse_upload(file_format(args.file.name, None), args.file.read_bytes())
        return asyncio.run(_seed(rows, args.file))
    except AppError as exc:
        logger.error(exc.message)
        return 1
    except OSError as exc:
        logger.error(f"Cannot read {args.file}: {exc.strerror}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
