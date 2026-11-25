import uuid
from datetime import UTC, datetime

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_admin_repository, get_current_admin
from app.core.config import Settings
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from app.main import create_app
from app.models.admin import Admin

PASSWORD = "correct-horse-battery"
SETTINGS = Settings(_env_file=None, jwt_secret="z" * 48, cors_origins="http://localhost:3000")
OTHER_SETTINGS = Settings(_env_file=None, jwt_secret="q" * 48, cors_origins="http://localhost:3000")


class FakeRepo:
    def __init__(self, *admins: Admin) -> None:
        self.admins = {a.id: a for a in admins}

    async def get(self, admin_id: uuid.UUID) -> Admin | None:
        return self.admins.get(admin_id)

    async def get_by_email(self, email: str) -> Admin | None:
        return next((a for a in self.admins.values() if a.email == email), None)


def make_admin(is_active: bool = True) -> Admin:
    return Admin(
        id=uuid.uuid4(),
        email="admin@example.com",
        password_hash=hash_password(PASSWORD),
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


def client_for(repo: FakeRepo) -> TestClient:
    app = create_app(SETTINGS)
    app.dependency_overrides[get_admin_repository] = lambda: repo
    return TestClient(app)


def test_login_returns_access_and_refresh_tokens() -> None:
    admin = make_admin()
    response = client_for(FakeRepo(admin)).post(
        "/api/v1/auth/login", json={"email": " Admin@Example.com ", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == SETTINGS.jwt_access_token_expire_minutes * 60
    access = decode_token(body["access_token"], TokenType.ACCESS, SETTINGS)
    refresh = decode_token(body["refresh_token"], TokenType.REFRESH, SETTINGS)
    assert access["sub"] == refresh["sub"] == str(admin.id)


@pytest.mark.parametrize(
    ("email", "password", "active"),
    [
        ("admin@example.com", "wrong-password", True),
        ("nobody@example.com", PASSWORD, True),
        ("admin@example.com", PASSWORD, False),
        ("admin@example.com", "x" * 200, True),  # > 72 bytes must not 500
    ],
)
def test_login_failures_are_indistinguishable(email: str, password: str, active: bool) -> None:
    response = client_for(FakeRepo(make_admin(active))).post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 401
    error = response.json()["error"]
    assert (error["code"], error["message"]) == ("invalid_credentials", "Invalid email or password")


def test_login_validation_error_does_not_echo_password() -> None:
    response = client_for(FakeRepo()).post(
        "/api/v1/auth/login", json={"password": "hunter2-secret"}
    )
    assert response.status_code == 422
    assert "hunter2-secret" not in response.text


def test_refresh_issues_new_tokens() -> None:
    admin = make_admin()
    response = client_for(FakeRepo(admin)).post(
        "/api/v1/auth/refresh",
        json={"refresh_token": create_refresh_token(str(admin.id), SETTINGS)},
    )
    assert response.status_code == 200
    claims = decode_token(response.json()["access_token"], TokenType.ACCESS, SETTINGS)
    assert claims["sub"] == str(admin.id)


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda admin_id: create_access_token(admin_id, SETTINGS),  # wrong type
        lambda admin_id: create_refresh_token(str(uuid.uuid4()), SETTINGS),  # unknown admin
        lambda admin_id: create_refresh_token("not-a-uuid", SETTINGS),
        lambda admin_id: "garbage",
    ],
)
def test_refresh_rejects_bad_tokens(token_factory: object) -> None:
    admin = make_admin()
    token = token_factory(str(admin.id))  # type: ignore[operator]
    response = client_for(FakeRepo(admin)).post(
        "/api/v1/auth/refresh", json={"refresh_token": token}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_refresh_rejects_inactive_admin() -> None:
    admin = make_admin(is_active=False)
    response = client_for(FakeRepo(admin)).post(
        "/api/v1/auth/refresh",
        json={"refresh_token": create_refresh_token(str(admin.id), SETTINGS)},
    )
    assert response.status_code == 401


def test_me_returns_current_admin() -> None:
    admin = make_admin()
    token = create_access_token(str(admin.id), SETTINGS)
    response = client_for(FakeRepo(admin)).get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(admin.id)
    assert body["email"] == admin.email
    assert "password_hash" not in body


def test_me_without_authorization_header_is_401() -> None:
    response = client_for(FakeRepo()).get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


@pytest.mark.parametrize(
    "header",
    [
        lambda admin_id: f"Bearer {create_refresh_token(admin_id, SETTINGS)}",  # wrong type
        lambda admin_id: f"Bearer {create_access_token(str(uuid.uuid4()), SETTINGS)}",  # deleted
        lambda admin_id: f"Bearer {create_access_token(admin_id, OTHER_SETTINGS)}",  # bad sig
        lambda admin_id: "Bearer not.a.jwt",
        lambda admin_id: "Basic dXNlcjpwYXNz",
    ],
)
def test_me_rejects_bad_tokens(header: object) -> None:
    admin = make_admin()
    response = client_for(FakeRepo(admin)).get(
        "/api/v1/auth/me",
        headers={"Authorization": header(str(admin.id))},  # type: ignore[operator]
    )
    assert response.status_code == 401


def test_me_inactive_admin_is_403() -> None:
    admin = make_admin(is_active=False)
    token = create_access_token(str(admin.id), SETTINGS)
    response = client_for(FakeRepo(admin)).get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_every_admin_route_requires_current_admin() -> None:
    for route in create_app(SETTINGS).routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/admin"):
            assert any(d.call is get_current_admin for d in route.dependant.dependencies)


def test_openapi_exposes_bearer_auth_for_swagger() -> None:
    schema = client_for(FakeRepo()).get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
