"""Create an admin account.

Usage::

    python -m app.scripts.create_admin --email admin@example.com --password '...'

``--email`` / ``--password`` fall back to ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD`` (for docker),
then to an interactive prompt. Exits 0 if the admin already exists, so it is safe to re-run.
The password is never logged or printed.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
import sys

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory
from app.repositories.admin_repository import AdminRepository
from app.services.admin_service import AdminService

logger = logging.getLogger("app.scripts.create_admin")


async def _create(email: str, password: str) -> None:
    engine = create_engine(get_settings())
    try:
        async with create_session_factory(engine)() as session:
            admin = await AdminService(AdminRepository(session)).create_admin(email, password)
        logger.info("Admin created", extra={"admin_id": str(admin.id), "email": admin.email})
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an admin account.")
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
    args = parser.parse_args(argv)

    configure_logging(get_settings().log_level.value)
    email = args.email or input("Admin email: ")
    password = args.password or getpass.getpass("Admin password: ")

    try:
        asyncio.run(_create(email, password))
    except ConflictError as exc:
        logger.info(exc.message)
    except AppError as exc:
        logger.error(exc.message)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
