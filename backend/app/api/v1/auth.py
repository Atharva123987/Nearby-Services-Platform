from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.login(body.email, body.password.get_secret_value())


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.refresh(body.refresh_token)
