import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_service_service
from app.schemas.service import ServiceRead
from app.services.service_service import ServiceService

router = APIRouter(prefix="/services", tags=["services"])

ServiceServiceDep = Annotated[ServiceService, Depends(get_service_service)]


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(service_id: uuid.UUID, service: ServiceServiceDep) -> ServiceRead:
    return await service.get(service_id)
