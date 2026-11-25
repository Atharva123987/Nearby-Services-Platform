"""Service request/response contracts and input validation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.service import ServiceCategory

NAME_MAX_LENGTH = 200
METADATA_MAX_BYTES = 10 * 1024
_RATING_STEP = Decimal("0.1")

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


def parse_category(value: object) -> ServiceCategory:
    """Case-insensitive, tolerant of a plural "s" ("ATM", "atm", "Atms" -> atm)."""
    if isinstance(value, ServiceCategory):
        return value
    if not isinstance(value, str):
        raise ValueError("category must be a string")
    key = value.strip().lower()
    for candidate in (key, key.removesuffix("s")):
        try:
            return ServiceCategory(candidate)
        except ValueError:
            continue
    allowed = ", ".join(c.value for c in ServiceCategory)
    raise ValueError(f"unknown category {value!r}; expected one of: {allowed}")


class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: ServiceCategory
    latitude: Latitude
    longitude: Longitude
    rating: Decimal | None = Field(default=None, ge=0, le=5, allow_inf_nan=False)
    metadata: dict[str, Any] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        if not 1 <= len(value) <= NAME_MAX_LENGTH:
            raise ValueError(f"name must be 1-{NAME_MAX_LENGTH} characters after trimming")
        return value

    @field_validator("category", mode="before")
    @classmethod
    def _parse_category(cls, value: object) -> ServiceCategory:
        return parse_category(value)

    @field_validator("rating")
    @classmethod
    def _check_rating_precision(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value != value.quantize(_RATING_STEP):
            raise ValueError("rating allows at most one decimal place")
        return value

    @field_validator("metadata")
    @classmethod
    def _check_metadata_size(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None:
            size = len(json.dumps(value, separators=(",", ":")).encode())
            if size > METADATA_MAX_BYTES:
                raise ValueError(f"metadata must be at most {METADATA_MAX_BYTES} bytes as JSON")
        return value


class ServiceRead(BaseModel):
    id: uuid.UUID
    name: str
    category: ServiceCategory
    latitude: float
    longitude: float
    rating: Decimal | None
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
