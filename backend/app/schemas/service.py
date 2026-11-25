"""Service request/response contracts and input validation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

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


def _trim(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _check_name(value: str) -> str:
    if not 1 <= len(value) <= NAME_MAX_LENGTH:
        raise ValueError(f"name must be 1-{NAME_MAX_LENGTH} characters after trimming")
    return value


def _check_rating_precision(value: Decimal | None) -> Decimal | None:
    if value is not None and value != value.quantize(_RATING_STEP):
        raise ValueError("rating allows at most one decimal place")
    return value


def _check_metadata_size(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is not None:
        size = len(json.dumps(value, separators=(",", ":")).encode())
        if size > METADATA_MAX_BYTES:
            raise ValueError(f"metadata must be at most {METADATA_MAX_BYTES} bytes as JSON")
    return value


# Query-param version of the category: same tolerant parsing, 422 lists the allowed values.
CategoryParam = Annotated[ServiceCategory, BeforeValidator(parse_category)]

PAGE_SIZE_MAX = 200
# Upper bound on the nearby search radius, so a request can't scan the whole table.
RADIUS_KM_MAX = 50


class NearbyQuery(BaseModel):
    """Query params for GET /services/nearby."""

    lat: Latitude
    lng: Longitude
    radius_km: float = Field(default=5, gt=0, le=RADIUS_KM_MAX, allow_inf_nan=False)
    category: CategoryParam | None = None
    limit: int = Field(default=20, ge=1, le=PAGE_SIZE_MAX)
    offset: int = Field(default=0, ge=0)


class BBox(BaseModel):
    """Map viewport. Boxes crossing the antimeridian (min_lng > max_lng) are not supported."""

    min_lng: Longitude
    min_lat: Latitude
    max_lng: Longitude
    max_lat: Latitude

    @model_validator(mode="after")
    def _check_order(self) -> BBox:
        if self.min_lng > self.max_lng:
            raise ValueError("min_lng must be <= max_lng (antimeridian-crossing boxes unsupported)")
        if self.min_lat > self.max_lat:
            raise ValueError("min_lat must be <= max_lat")
        return self

    @classmethod
    def parse(cls, value: str) -> BBox:
        """Parse "minLng,minLat,maxLng,maxLat". Raises ValueError (incl. pydantic ValidationError)."""
        parts = value.split(",")
        if len(parts) != 4:
            raise ValueError("bbox must be minLng,minLat,maxLng,maxLat")
        keys = ("min_lng", "min_lat", "max_lng", "max_lat")
        return cls.model_validate(dict(zip(keys, (p.strip() for p in parts), strict=True)))


class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: ServiceCategory
    latitude: Latitude
    longitude: Longitude
    rating: Decimal | None = Field(default=None, ge=0, le=5, allow_inf_nan=False)
    metadata: dict[str, Any] | None = None

    _trim_name = field_validator("name", mode="before")(_trim)
    _name = field_validator("name")(_check_name)
    _category = field_validator("category", mode="before")(parse_category)
    _rating = field_validator("rating")(_check_rating_precision)
    _metadata = field_validator("metadata")(_check_metadata_size)


class ServiceUpdate(BaseModel):
    """PATCH body: only the fields sent are changed. rating/metadata may be set to null."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    category: ServiceCategory | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    rating: Decimal | None = Field(default=None, ge=0, le=5, allow_inf_nan=False)
    metadata: dict[str, Any] | None = None

    _trim_name = field_validator("name", mode="before")(_trim)
    _rating = field_validator("rating")(_check_rating_precision)
    _metadata = field_validator("metadata")(_check_metadata_size)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _check_name(value)

    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, value: object) -> ServiceCategory | None:
        return None if value is None else parse_category(value)

    @model_validator(mode="after")
    def _check_fields(self) -> ServiceUpdate:
        for field in ("name", "category", "latitude", "longitude"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if ("latitude" in self.model_fields_set) != ("longitude" in self.model_fields_set):
            raise ValueError("latitude and longitude must be sent together")
        return self


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


class ServicePage(BaseModel):
    items: list[ServiceRead]
    page: int
    page_size: int
    total: int


class NearbyServiceRead(ServiceRead):
    distance_m: float


class NearbyPage(BaseModel):
    items: list[NearbyServiceRead]
    limit: int
    offset: int
    total: int
