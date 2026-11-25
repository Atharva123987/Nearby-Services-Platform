"""Application settings.

Sources, lowest to highest precedence: field defaults -> ``.env`` -> ``.env.<APP_ENV>`` ->
process environment. Every variable is documented in the repo-root ``.env.example``.
"""

from __future__ import annotations

import ipaddress
import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from dotenv import dotenv_values
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/core/config.py -> repo root. In the container this resolves to "/", where no
# .env files exist and configuration comes from the environment alone.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Secrets that must never be accepted in production.
DEV_JWT_SECRET = "dev-insecure-jwt-secret-change-me"  # noqa: S105
KNOWN_DEFAULT_SECRETS = frozenset(
    {
        "",
        DEV_JWT_SECRET,
        "change-me",
        "changeme",
        "secret",
        "jwt-secret",
        "replace-me-with-a-long-random-string",
    }
)
MIN_PROD_SECRET_LENGTH = 32


class AppEnv(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def _resolve_app_env() -> str:
    """APP_ENV picks which ``.env.<APP_ENV>`` file is loaded, so it is resolved first."""
    env = os.environ.get("APP_ENV") or dotenv_values(_REPO_ROOT / ".env").get("APP_ENV")
    return (env or AppEnv.DEV.value).lower()


def _env_files() -> tuple[Path, ...]:
    return (_REPO_ROOT / ".env", _REPO_ROOT / f".env.{_resolve_app_env()}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---------------------------------------------------------------
    app_env: AppEnv = AppEnv.DEV
    app_name: str = "Fieldguide API"
    log_level: LogLevel = LogLevel.INFO

    # --- Database ----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://fieldguide:fieldguide@localhost:5432/fieldguide"
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    db_echo: bool = False

    # --- Redis -------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    redis_socket_timeout_seconds: float = Field(default=1.0, gt=0)

    # --- Auth --------------------------------------------------------------
    jwt_secret: SecretStr = SecretStr(DEV_JWT_SECRET)
    # Pinned: tokens are only ever signed/verified with HS256 (rejects `alg: none`).
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1)
    jwt_refresh_token_expire_days: int = Field(default=7, ge=1)

    # --- Rate limiting (requests per minute, per client) --------------------
    rate_limit_enabled: bool = True
    rate_limit_default_per_minute: int = Field(default=120, ge=1)
    rate_limit_auth_per_minute: int = Field(default=10, ge=1)
    # Proxy IPs/CIDRs whose X-Forwarded-For we trust. Empty => header ignored (spoofable).
    trusted_proxies: Annotated[list[str], NoDecode] = []

    # --- Cache TTLs (seconds) -----------------------------------------------
    cache_ttl_default_seconds: int = Field(default=300, ge=0)
    cache_ttl_search_seconds: int = Field(default=60, ge=0)
    cache_ttl_service_detail_seconds: int = Field(default=600, ge=0)
    cache_ttl_empty_seconds: int = Field(default=15, ge=0)

    # --- HTTP --------------------------------------------------------------
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    ready_check_timeout_seconds: float = Field(default=2.0, gt=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string (``a,b``) as well as a list."""
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def _split_proxies(cls, value: object) -> object:
        if isinstance(value, str):
            return [proxy.strip() for proxy in value.split(",") if proxy.strip()]
        return value

    @field_validator("trusted_proxies")
    @classmethod
    def _validate_proxies(cls, value: list[str]) -> list[str]:
        for proxy in value:
            ipaddress.ip_network(proxy, strict=False)  # raises ValueError if malformed
        return value

    @model_validator(mode="after")
    def _enforce_prod_safety(self) -> Self:
        if self.app_env is not AppEnv.PROD:
            return self
        problems: list[str] = []
        secret = self.jwt_secret.get_secret_value()
        if secret.strip().lower() in KNOWN_DEFAULT_SECRETS:
            problems.append("JWT_SECRET is missing or set to a known default")
        elif len(secret) < MIN_PROD_SECRET_LENGTH:
            problems.append(f"JWT_SECRET must be at least {MIN_PROD_SECRET_LENGTH} characters")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must list explicit origins, not '*'")
        if problems:
            raise ValueError("Refusing to start in prod: " + "; ".join(problems))
        return self

    @property
    def is_prod(self) -> bool:
        return self.app_env is AppEnv.PROD


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=_env_files())
