"""Coordinate helpers. PostGIS points are (X, Y) = (longitude, latitude)."""

from __future__ import annotations

import math

from geoalchemy2 import WKTElement

SRID_WGS84 = 4326


def validate_coordinates(lat: float, lng: float) -> None:
    """Raise ValueError unless lat is in [-90, 90] and lng in [-180, 180] (finite)."""
    if not (math.isfinite(lat) and math.isfinite(lng)):
        raise ValueError("coordinates must be finite numbers")
    if not -90.0 <= lat <= 90.0:
        raise ValueError("latitude must be between -90 and 90")
    if not -180.0 <= lng <= 180.0:
        raise ValueError("longitude must be between -180 and 180")


def point_wkt(lat: float, lng: float) -> str:
    """WKT for a point. Note the order: longitude first, then latitude."""
    validate_coordinates(lat, lng)
    return f"POINT({lng!r} {lat!r})"


def make_point(lat: float, lng: float) -> WKTElement:
    return WKTElement(point_wkt(lat, lng), srid=SRID_WGS84)
