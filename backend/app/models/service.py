"""Nearby service (hospital, ATM, shop, ...) with a geographic point location."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceCategory(StrEnum):
    HOSPITAL = "hospital"
    ATM = "atm"
    SHOP = "shop"
    OTHER = "other"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[ServiceCategory] = mapped_column(
        Enum(
            ServiceCategory,
            name="service_category",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    # geography (metres), not geometry (degrees). PostGIS points are (X=lng, Y=lat).
    # spatial_index=False: the GiST index is declared explicitly in __table_args__.
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1), nullable=True)
    # `metadata` is reserved on declarative classes, so the attribute is `meta`.
    # none_as_null: Python None -> SQL NULL (not JSON null, which the check would reject).
    meta: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB(none_as_null=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 200", name="ck_services_name_length"
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)", name="ck_services_rating_range"
        ),
        CheckConstraint(
            "metadata IS NULL OR jsonb_typeof(metadata) = 'object'",
            name="ck_services_metadata_object",
        ),
        Index("ix_services_location", "location", postgresql_using="gist"),
        Index("ix_services_category", "category"),
        Index("ix_services_created_at", "created_at"),
    )
    # Fetch server-generated id/timestamps via RETURNING (no implicit lazy load under asyncio).
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
