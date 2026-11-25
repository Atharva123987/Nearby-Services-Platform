"""Login and token refresh for admins."""

from __future__ import annotations

import uuid
from functools import cache
from typing import Protocol

from app.core.config import Settings
from app.core.errors import ForbiddenError
from app.core.security import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.admin import Admin
from app.schemas.admin import normalize_email
from app.schemas.auth import TokenResponse


class AuthRepositoryProtocol(Protocol):
    async def get(self, admin_id: uuid.UUID) -> Admin | None: ...
    async def get_by_email(self, email: str) -> Admin | None: ...


@cache
def _dummy_hash() -> str:
    """Checked against when the email is unknown, so both paths cost one bcrypt check."""
    return hash_password("dummy-password-for-timing")


class AuthService:
    def __init__(self, repository: AuthRepositoryProtocol, settings: Settings) -> None:
        self._repo = repository
        self._settings = settings

    async def login(self, email: str, password: str) -> TokenResponse:
        admin = await self._repo.get_by_email(normalize_email(email))
        password_ok = verify_password(password, admin.password_hash if admin else _dummy_hash())
        if admin is None or not password_ok or not admin.is_active:
            raise InvalidCredentialsError("Invalid email or password")
        return self._issue(admin)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        admin = await self._admin_from_token(refresh_token, TokenType.REFRESH)
        if not admin.is_active:
            raise InvalidTokenError("Invalid token")
        return self._issue(admin)

    async def get_current_admin(self, access_token: str) -> Admin:
        admin = await self._admin_from_token(access_token, TokenType.ACCESS)
        if not admin.is_active:
            raise ForbiddenError("Admin account is inactive")
        return admin

    async def _admin_from_token(self, token: str, token_type: TokenType) -> Admin:
        """Admin the token's ``sub`` points to; 401 if the token is bad or the admin is gone."""
        claims = decode_token(token, token_type, self._settings)
        try:
            admin_id = uuid.UUID(claims["sub"])
        except ValueError as exc:
            raise InvalidTokenError("Invalid token") from exc
        admin = await self._repo.get(admin_id)
        if admin is None:
            raise InvalidTokenError("Invalid token")
        return admin

    def _issue(self, admin: Admin) -> TokenResponse:
        subject = str(admin.id)
        return TokenResponse(
            access_token=create_access_token(subject, self._settings),
            refresh_token=create_refresh_token(subject, self._settings),
            expires_in=self._settings.jwt_access_token_expire_minutes * 60,
        )
