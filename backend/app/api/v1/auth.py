from fastapi import APIRouter, Request, Response

from app.api.deps import (
    AuthServiceDep,
    CurrentAdminDep,
    SettingsDep,
    enforce_login_rate_limit,
    reset_login_email_rate_limit,
)
from app.schemas.admin import AdminRead
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    service: AuthServiceDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
) -> TokenResponse:
    # Every attempt counts (failed ones included); success clears the per-email counter.
    await enforce_login_rate_limit(request, response, settings, body.email)
    tokens = await service.login(body.email, body.password.get_secret_value())
    await reset_login_email_rate_limit(request, settings, body.email)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.refresh(body.refresh_token)


@router.get("/me", response_model=AdminRead)
async def me(admin: CurrentAdminDep) -> AdminRead:
    return AdminRead.model_validate(admin)
