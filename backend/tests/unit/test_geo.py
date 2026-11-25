import math

import pytest

from app.utils.geo import make_point, point_wkt


def test_point_is_lng_then_lat() -> None:
    # Delhi: lat 28.6139, lng 77.209. PostGIS wants X=lng, Y=lat.
    assert point_wkt(lat=28.6139, lng=77.209) == "POINT(77.209 28.6139)"
    point = make_point(lat=28.6139, lng=77.209)
    assert point.srid == 4326
    assert point.data == "POINT(77.209 28.6139)"


@pytest.mark.parametrize(
    ("lat", "lng"),
    [(91, 0), (-90.0001, 0), (0, 180.5), (0, -181), (math.nan, 0), (0, math.inf)],
)
def test_rejects_invalid_coordinates(lat: float, lng: float) -> None:
    with pytest.raises(ValueError):
        point_wkt(lat=lat, lng=lng)


def test_accepts_boundaries() -> None:
    assert point_wkt(lat=-90, lng=180) == "POINT(180 -90)"
