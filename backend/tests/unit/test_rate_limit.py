import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.api.deps import (
    default_rate_limit,
    get_admin_repository,
    get_current_admin,
    get_db_session,
)
from app.core.config import Settings
from app.core.rate_limit import client_ip
from app.main import create_app
from tests.unit.test_auth import PASSWORD, FakeRepo, make_admin

PROXIES = ["10.0.0.0/8"]
ADMIN = make_admin()


def test_ignores_forwarded_for_without_trusted_proxies() -> None:
    assert client_ip("1.2.3.4", "9.9.9.9", []) == "1.2.3.4"


def test_ignores_forwarded_for_from_untrusted_peer() -> None:
    assert client_ip("1.2.3.4", "9.9.9.9", PROXIES) == "1.2.3.4"


def test_uses_first_untrusted_hop_from_the_right() -> None:
    # Left-most entry is client-controlled (spoofed); 5.6.7.8 is what our proxy saw.
    assert client_ip("10.0.0.1", "6.6.6.6, 5.6.7.8, 10.0.0.2", PROXIES) == "5.6.7.8"


class FakePipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self.redis = redis
        self.keys: list[str] = []

    async def __aenter__(self) -> "FakePipeline":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def incr(self, key: str) -> None:
        self.keys.append(key)

    def expire(self, key: str, seconds: int) -> None:
        pass

    async def execute(self) -> list[int]:
        if self.redis.down:
            raise RedisConnectionError("down")
        key = self.keys[0]
        self.redis.counts[key] = self.redis.counts.get(key, 0) + 1
        return [self.redis.counts[key], 1]


class FakeRedis:
    def __init__(self, down: bool = False) -> None:
        self.down = down
        self.counts: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        return FakePipeline(self)

    async def delete(self, key: str) -> None:
        self.counts.pop(key, None)


@pytest.fixture(autouse=True)
def low_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    # Limits come from env, as in production; tests just set them low.
    for name, value in {
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_DEFAULT_PER_MINUTE": "2",
        "RATE_LIMIT_NEARBY_PER_MINUTE": "1",
        "RATE_LIMIT_ADMIN_WRITE_PER_MINUTE": "1",
        "RATE_LIMIT_LOGIN_PER_MINUTE": "2",
        "RATE_LIMIT_LOGIN_PER_HOUR": "100",
    }.items():
        monkeypatch.setenv(name, value)


def build(redis: FakeRedis) -> FastAPI:
    app = create_app(Settings(_env_file=None, jwt_secret="y" * 48))
    app.state.redis = redis
    # No DB in unit tests; the requests below fail validation before touching it.
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[get_current_admin] = lambda: None
    app.dependency_overrides[get_admin_repository] = lambda: FakeRepo(ADMIN)
    return app


def test_default_limit_returns_429_with_retry_after() -> None:
    client = TestClient(build(FakeRedis()))
    codes = [client.get("/api/v1/services/not-a-uuid").status_code for _ in range(3)]
    assert codes[:2] == [422, 422]
    assert codes[2] == 429
    response = client.get("/api/v1/services/not-a-uuid")
    assert response.json()["error"]["code"] == "too_many_requests"
    assert 0 < int(response.headers["Retry-After"]) <= 60
    assert response.headers["X-RateLimit-Limit"] == "2"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert int(response.headers["X-RateLimit-Reset"]) % 60 == 0


def test_window_reset_allows_requests_again(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1_800_000_000.0]
    monkeypatch.setattr("time.time", lambda: now[0])
    client = TestClient(build(FakeRedis()))
    assert client.get("/api/v1/services/nearby").status_code == 422
    assert client.get("/api/v1/services/nearby").status_code == 429
    now[0] += 60
    assert client.get("/api/v1/services/nearby").status_code == 422


def test_nearby_tier_is_stricter_than_default() -> None:
    client = TestClient(build(FakeRedis()))
    first = client.get("/api/v1/services/nearby")
    assert first.status_code == 422
    # Default tier is 2/min, so this 429 comes from the nearby tier (1/min).
    assert client.get("/api/v1/services/nearby").status_code == 429


def test_admin_write_tier() -> None:
    client = TestClient(build(FakeRedis()))
    assert client.post("/api/v1/admin/services", json={}).status_code == 422
    assert client.post("/api/v1/admin/services", json={}).status_code == 429


def test_success_response_has_rate_limit_headers() -> None:
    app = build(FakeRedis())

    @app.get("/ping", dependencies=[Depends(default_rate_limit)])
    async def ping() -> dict[str, str]:
        return {}

    response = TestClient(app).get("/ping")
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "2"
    assert response.headers["X-RateLimit-Remaining"] == "1"


def test_health_is_exempt() -> None:
    client = TestClient(build(FakeRedis()))
    assert all(client.get("/health").status_code == 200 for _ in range(5))


def test_redis_down_fails_open_for_public_routes() -> None:
    client = TestClient(build(FakeRedis(down=True)))
    assert client.get("/api/v1/services/not-a-uuid").status_code == 422


def test_redis_down_fails_closed_for_login() -> None:
    client = TestClient(build(FakeRedis(down=True)))
    response = client.post("/api/v1/auth/login", json={"email": "a@b.co", "password": "x"})
    assert response.status_code == 503


def login(client: TestClient, email: str, password: str = "wrong") -> int:  # noqa: S107
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    status: int = response.status_code
    return status


def client_from(app: FastAPI, ip: str) -> TestClient:
    return TestClient(app, client=(ip, 50000))


def test_login_limited_per_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "100")
    client = client_from(build(FakeRedis()), "1.1.1.1")
    # Different emails each time: the per-IP counter still trips.
    assert [login(client, f"u{i}@example.com") for i in range(3)] == [401, 401, 429]


def test_login_limited_per_email_across_ips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "100")
    app = build(FakeRedis())
    codes = [login(client_from(app, f"1.1.1.{i}"), "victim@example.com") for i in range(3)]
    assert codes == [401, 401, 429]
    # The email key is normalised, so case/whitespace changes don't dodge it.
    assert login(client_from(app, "1.1.1.9"), " VICTIM@example.com ") == 429


def test_successful_login_resets_email_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "100")
    app = build(FakeRedis())
    email = ADMIN.email
    assert login(client_from(app, "2.2.2.1"), email) == 401
    assert login(client_from(app, "2.2.2.1"), email, PASSWORD) == 200
    # Without the reset, the second of these would be the email's 4th attempt (> 2).
    assert login(client_from(app, "2.2.2.2"), email) == 401
    assert login(client_from(app, "2.2.2.3"), email) == 401
    assert login(client_from(app, "2.2.2.4"), email) == 429


def test_login_hourly_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "100")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_MINUTE", "100")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_HOUR", "2")
    client = client_from(build(FakeRedis()), "3.3.3.3")
    assert [login(client, "a@example.com") for _ in range(2)] == [401, 401]
    response = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "x"})
    assert response.status_code == 429
    assert response.headers["X-RateLimit-Limit"] == "2"
    assert 0 < int(response.headers["Retry-After"]) <= 3600
