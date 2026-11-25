"""/api/v1/admin/* routes. Every route on this router requires an authenticated, active admin."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import ServiceServiceDep, admin_write_rate_limit, get_current_admin
from app.schemas.service import (
    NAME_MAX_LENGTH,
    PAGE_SIZE_MAX,
    CategoryParam,
    ServiceCreate,
    ServicePage,
    ServiceRead,
    ServiceUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])
write_limit = [Depends(admin_write_rate_limit)]


@router.get("/services", response_model=ServicePage)
async def list_services(
    service: ServiceServiceDep,
    search: Annotated[str | None, Query(max_length=NAME_MAX_LENGTH)] = None,
    category: CategoryParam | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = 20,
) -> ServicePage:
    """`search` is a case-insensitive substring match on the name."""
    return await service.list(page, page_size, category=category, search=search)


@router.post(
    "/services",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=write_limit,
)
async def create_service(body: ServiceCreate, service: ServiceServiceDep) -> ServiceRead:
    """409 if a service with the same name already exists within 10 m."""
    return await service.create(body)


@router.patch("/services/{service_id}", response_model=ServiceRead, dependencies=write_limit)
async def update_service(
    service_id: uuid.UUID, body: ServiceUpdate, service: ServiceServiceDep
) -> ServiceRead:
    """Only sent fields change. latitude and longitude must be sent together."""
    return await service.update(service_id, body)


@router.delete(
    "/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=write_limit,
)
async def delete_service(service_id: uuid.UUID, service: ServiceServiceDep) -> Response:
    """Repeating a delete returns 404 (the service is already gone)."""
    await service.delete(service_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
