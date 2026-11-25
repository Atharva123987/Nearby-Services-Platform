from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import DEV_JWT_SECRET, AppEnv, Settings

STRONG_SECRET = "x" * 48


def make(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_dev_allows_default_secret() -> None:
    settings = make(app_env="dev")
    assert settings.jwt_secret.get_secret_value() == DEV_JWT_SECRET


@pytest.mark.parametrize("secret", [None, DEV_JWT_SECRET, "change-me", "short-but-unique"])
def test_prod_rejects_missing_default_or_short_secret(secret: str | None) -> None:
    overrides: dict[str, object] = {"app_env": "prod"}
    if secret is not None:
        overrides["jwt_secret"] = secret
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(**overrides)


def test_prod_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        make(app_env="prod", jwt_secret=STRONG_SECRET, cors_origins="*")


def test_prod_accepts_strong_config() -> None:
    settings = make(app_env="prod", jwt_secret=STRONG_SECRET, cors_origins="https://a.example")
    assert settings.app_env is AppEnv.PROD
    assert settings.is_prod


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.example/")
    assert make().cors_origins == ["http://localhost:3000", "https://app.example"]
