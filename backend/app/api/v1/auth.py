from fastapi import APIRouter, Depends

from app.api.deps import AuthServiceDep, CurrentAdminDep, auth_rate_limit
from app.schemas.admin import AdminRead
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def login(body: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.login(body.email, body.password.get_secret_value())


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.refresh(body.refresh_token)


@router.get("/me", response_model=AdminRead)
async def me(admin: CurrentAdminDep) -> AdminRead:
    return AdminRead.model_validate(admin)
