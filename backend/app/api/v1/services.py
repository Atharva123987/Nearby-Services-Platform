import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.deps import ServiceServiceDep, nearby_rate_limit
from app.schemas.service import (
    PAGE_SIZE_MAX,
    BBox,
    CategoryParam,
    MarkerArea,
    NearbyMarkers,
    NearbyPage,
    NearbyQuery,
    ServicePage,
    ServiceRead,
)

router = APIRouter(prefix="/services", tags=["services"])


def parse_bbox(
    bbox: Annotated[
        str | None,
        Query(description="minLng,minLat,maxLng,maxLat", examples=["77.1,28.5,77.3,28.7"]),
    ] = None,
) -> BBox | None:
    if bbox is None:
        return None
    try:
        return BBox.parse(bbox)
    except ValidationError as exc:
        errors = [
            {"loc": ("query", "bbox", *e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        raise RequestValidationError(errors) from exc
    except ValueError as exc:
        raise RequestValidationError(
            [{"loc": ("query", "bbox"), "msg": str(exc), "type": "value_error"}]
        ) from exc


@router.get("", response_model=ServicePage)
async def list_services(
    service: ServiceServiceDep,
    response: Response,
    bbox: Annotated[BBox | None, Depends(parse_bbox)],
    category: CategoryParam | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = 20,
) -> ServicePage:
    """`bbox` limits results to services inside the map viewport (edges included)."""
    result, hit = await service.cached_list(page, page_size, category=category, bbox=bbox)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return result


@router.get("/nearby", response_model=NearbyPage, dependencies=[Depends(nearby_rate_limit)])
async def nearby_services(
    service: ServiceServiceDep, query: Annotated[NearbyQuery, Query()], response: Response
) -> NearbyPage:
    """Services within `radius_km` of (`lat`, `lng`), nearest first."""
    page, hit = await service.nearby(query)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return page


@router.get("/nearby/markers", dependencies=[Depends(nearby_rate_limit)])
async def nearby_markers(
    service: ServiceServiceDep, area: Annotated[MarkerArea, Query()], response: Response
) -> NearbyMarkers:
    """All matching pins, nearest first, without detail metadata or timestamps."""
    markers, hit = await service.nearby_markers(area)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return markers


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(
    service_id: uuid.UUID, service: ServiceServiceDep, response: Response
) -> ServiceRead:
    result, hit = await service.cached_get(service_id)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return result
