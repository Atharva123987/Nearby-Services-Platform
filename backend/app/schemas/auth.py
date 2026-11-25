from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    # SecretStr keeps the password out of reprs and logs.
    password: SecretStr = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int  # access token lifetime, seconds
