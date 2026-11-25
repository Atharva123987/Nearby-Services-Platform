from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret-that-is-long-enough-for-hs256"


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret=SecretStr(SECRET))


def test_access_token_round_trip(settings: Settings) -> None:
    claims = decode_token(create_access_token("admin-1", settings), TokenType.ACCESS, settings)
    assert claims["sub"] == "admin-1"
    assert claims["type"] == "access"
    assert claims["exp"] - claims["iat"] == settings.jwt_access_token_expire_minutes * 60


def test_refresh_token_round_trip(settings: Settings) -> None:
    claims = decode_token(create_refresh_token("admin-1", settings), TokenType.REFRESH, settings)
    assert claims["type"] == "refresh"
    assert claims["exp"] - claims["iat"] == 7 * 24 * 3600


def test_wrong_token_type_rejected(settings: Settings) -> None:
    with pytest.raises(InvalidTokenError):
        decode_token(create_refresh_token("admin-1", settings), TokenType.ACCESS, settings)


def test_expired_token_rejected(settings: Settings) -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {"sub": "a", "type": "access", "iat": past, "exp": past + timedelta(minutes=1)},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError, match="expired"):
        decode_token(token, TokenType.ACCESS, settings)


def test_wrong_signature_rejected(settings: Settings) -> None:
    other = Settings(jwt_secret=SecretStr("another-secret-that-is-long-enough-x"))
    with pytest.raises(InvalidTokenError):
        decode_token(create_access_token("a", other), TokenType.ACCESS, settings)


def test_malformed_token_rejected(settings: Settings) -> None:
    with pytest.raises(InvalidTokenError):
        decode_token("not.a.jwt", TokenType.ACCESS, settings)


def test_alg_none_rejected(settings: Settings) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "a", "type": "access", "iat": now, "exp": now + timedelta(minutes=5)},
        None,
        algorithm="none",
    )
    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.ACCESS, settings)


def test_invalid_token_error_is_401() -> None:
    assert InvalidTokenError("x").status_code == 401


def test_algorithm_setting_is_pinned() -> None:
    with pytest.raises(ValueError):
        Settings(jwt_algorithm="none")


def test_password_hashing() -> None:
    hashed = hash_password("s3cret-pass")
    assert hashed != "s3cret-pass"
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong-pass", hashed)
