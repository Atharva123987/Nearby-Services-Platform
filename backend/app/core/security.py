"""Password hashing and JWT access/refresh token helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings
from app.core.errors import AppError

# bcrypt only looks at the first 72 bytes (and bcrypt>=5 raises beyond that).
MAX_PASSWORD_BYTES = 72


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class InvalidTokenError(AppError):
    """Token is expired, malformed, wrongly signed or of the wrong type."""

    status_code = 401
    code = "invalid_token"


class InvalidCredentialsError(AppError):
    """Login failed. One message for unknown email, wrong password and inactive admin."""

    status_code = 401
    code = "invalid_credentials"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check (bcrypt.checkpw)."""
    encoded = password.encode()
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode())


def _create_token(subject: str, token_type: TokenType, ttl: timedelta, settings: Settings) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def create_access_token(subject: str, settings: Settings) -> str:
    ttl = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return _create_token(subject, TokenType.ACCESS, ttl, settings)


def create_refresh_token(subject: str, settings: Settings) -> str:
    ttl = timedelta(days=settings.jwt_refresh_token_expire_days)
    return _create_token(subject, TokenType.REFRESH, ttl, settings)


def decode_token(token: str, expected_type: TokenType, settings: Settings) -> dict[str, Any]:
    """Return the claims of a valid token of ``expected_type`` or raise ``InvalidTokenError``."""
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            # Never trust the token header: only the pinned algorithm is accepted.
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid token") from exc
    if claims["type"] != expected_type.value:
        raise InvalidTokenError("Invalid token type")
    return claims
