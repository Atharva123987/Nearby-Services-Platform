from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_health_service
from app.core.config import Settings
from app.main import create_app
from app.schemas.health import CheckStatus, DependencyCheck, ReadinessResponse, ReadyStatus


def build(app_env: str = "dev") -> FastAPI:
    settings = Settings(
        _env_file=None,
        app_env=app_env,
        jwt_secret="y" * 48,
        cors_origins="http://localhost:3000",
    )
    app = create_app(settings)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    return app


def test_health_echoes_request_id() -> None:
    client = TestClient(build())
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "abc-123"


def test_generates_request_id_when_missing_or_unsafe() -> None:
    client = TestClient(build())
    response = client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert response.headers["X-Request-ID"] != "bad id\nwith newline"
    assert len(response.headers["X-Request-ID"]) == 32


def test_not_found_uses_error_envelope() -> None:
    client = TestClient(build())
    response = client.get("/nope", headers={"X-Request-ID": "rid-1"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "details": None,
            "request_id": "rid-1",
        }
    }


def test_unhandled_exception_hides_internals_in_prod() -> None:
    client = TestClient(build("prod"))
    response = client.get("/boom", headers={"X-Request-ID": "rid-2"})
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "rid-2"
    body = response.json()
    assert body["error"] == {
        "code": "internal_error",
        "message": "Internal server error",
        "details": None,
        "request_id": "rid-2",
    }
    assert "secret internals" not in response.text
    assert "Traceback" not in response.text


def test_cors_only_allows_configured_origins() -> None:
    client = TestClient(build())
    allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
    denied = client.get("/health", headers={"Origin": "https://evil.example"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


class FakeHealthService:
    def __init__(self, status: ReadyStatus) -> None:
        self.status = status

    async def readiness(self) -> ReadinessResponse:
        check = DependencyCheck(status=CheckStatus.OK)
        return ReadinessResponse(status=self.status, checks={"database": check})


def test_ready_status_codes() -> None:
    app = build()
    client = TestClient(app)
    expected = {ReadyStatus.OK: 200, ReadyStatus.DEGRADED: 200, ReadyStatus.UNAVAILABLE: 503}
    for ready_status, code in expected.items():
        app.dependency_overrides[get_health_service] = lambda s=ready_status: FakeHealthService(s)
        response = client.get("/ready")
        assert response.status_code == code
        assert response.json()["status"] == ready_status.value
