"""/api/v1/admin/* routes. Every route on this router requires an authenticated, active admin."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status

from app.api.deps import ServiceServiceDep, admin_write_rate_limit, get_current_admin
from app.schemas.service import (
    NAME_MAX_LENGTH,
    PAGE_SIZE_MAX,
    BulkUploadResult,
    CategoryParam,
    ServiceCreate,
    ServicePage,
    ServiceRead,
    ServiceUpdate,
)
from app.services.bulk_upload import CSV_TEMPLATE, MAX_UPLOAD_BYTES, file_format, parse_upload

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


@router.post("/services/bulk", response_model=BulkUploadResult, dependencies=write_limit)
async def bulk_upload_services(
    file: UploadFile,
    service: ServiceServiceDep,
    mode: Literal["partial", "strict"] = "partial",
) -> BulkUploadResult:
    """Multipart `file` (.csv or .json, max 5 MB / 10k rows). Extra columns are ignored.

    `partial` inserts the valid rows and reports the bad ones; `strict` inserts nothing if any
    row is bad. Rows are numbered from 1, excluding the CSV header.
    """
    fmt = file_format(file.filename, file.content_type)
    rows = parse_upload(fmt, await file.read(MAX_UPLOAD_BYTES + 1))
    return await service.bulk_create(rows, mode)


@router.get("/services/bulk/template", response_class=Response)
async def bulk_upload_template() -> Response:
    """CSV with the columns the bulk upload expects and one example row."""
    return Response(
        CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="services_template.csv"'},
    )


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
async def delete_service(service_id: uuid.UUID, service: ServiceServiceDep) -> None:
    """Repeating a delete returns 404 (the service is already gone)."""
    await service.delete(service_id)
