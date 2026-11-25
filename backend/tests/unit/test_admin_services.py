import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.deps import get_admin_repository, get_current_admin, get_service_repository
from app.core.config import Settings
from app.main import create_app
from app.models.admin import Admin
from tests.unit.test_service_service import FakeRepo

SETTINGS = Settings(_env_file=None, jwt_secret="z" * 48, cors_origins="http://localhost:3000")
BODY = {"name": "Corner ATM", "category": "atm", "latitude": 28.6, "longitude": 77.2}


def make_client(repo: FakeRepo) -> TestClient:
    app = create_app(SETTINGS)
    admin = Admin(
        id=uuid.uuid4(), email="a@example.com", is_active=True, created_at=datetime.now(UTC)
    )
    app.dependency_overrides[get_current_admin] = lambda: admin
    app.dependency_overrides[get_service_repository] = lambda: repo
    return TestClient(app)


def test_create_update_delete_flow() -> None:
    client = make_client(FakeRepo())
    created = client.post("/api/v1/admin/services", json=BODY)
    assert created.status_code == 201
    service_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/admin/services/{service_id}", json={"latitude": 10, "longitude": 20}
    )
    assert patched.status_code == 200
    assert (patched.json()["latitude"], patched.json()["longitude"]) == (10, 20)

    assert client.delete(f"/api/v1/admin/services/{service_id}").status_code == 204
    second = client.delete(f"/api/v1/admin/services/{service_id}")
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "not_found"


def test_duplicate_create_is_409() -> None:
    client = make_client(FakeRepo())
    assert client.post("/api/v1/admin/services", json=BODY).status_code == 201
    response = client.post("/api/v1/admin/services", json=BODY)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_unknown_id_is_404_and_invalid_uuid_is_422() -> None:
    client = make_client(FakeRepo())
    url = f"/api/v1/admin/services/{uuid.uuid4()}"
    assert client.patch(url, json={"name": "x"}).status_code == 404
    assert client.delete(url).status_code == 404
    assert client.patch("/api/v1/admin/services/not-a-uuid", json={"name": "x"}).status_code == 422
    assert client.delete("/api/v1/admin/services/not-a-uuid").status_code == 422


def test_patch_validation() -> None:
    client = make_client(FakeRepo())
    service_id = client.post("/api/v1/admin/services", json=BODY).json()["id"]
    url = f"/api/v1/admin/services/{service_id}"
    for body in ({"latitude": 1}, {"longitude": 1}, {"name": None}, {"unknown": 1}):
        assert client.patch(url, json=body).status_code == 422, body
    cleared = client.patch(url, json={"rating": None, "metadata": None})
    assert cleared.status_code == 200
    assert cleared.json()["rating"] is None


def test_admin_service_routes_require_auth() -> None:
    app = create_app(SETTINGS)
    app.dependency_overrides[get_admin_repository] = lambda: None  # never reached without a token
    app.dependency_overrides[get_service_repository] = FakeRepo
    client = TestClient(app)
    assert client.post("/api/v1/admin/services", json=BODY).status_code == 401
    assert client.delete(f"/api/v1/admin/services/{uuid.uuid4()}").status_code == 401
    assert client.get("/api/v1/admin/services").status_code == 401


def test_public_list_filters_by_category_and_paginates() -> None:
    client = make_client(FakeRepo())
    client.post("/api/v1/admin/services", json=BODY)
    client.post(
        "/api/v1/admin/services", json={**BODY, "name": "City Hospital", "category": "hospital"}
    )
    response = client.get("/api/v1/services", params={"category": "ATMs", "page_size": 1})
    assert response.status_code == 200
    body = response.json()
    assert (body["page"], body["page_size"], body["total"]) == (1, 1, 1)
    assert body["items"][0]["name"] == "Corner ATM"
    assert client.get("/api/v1/services", params={"page": 5}).json()["items"] == []


def test_public_list_rejects_bad_params() -> None:
    client = make_client(FakeRepo())
    for params in ({"page": 0}, {"page_size": 0}, {"page_size": 201}, {"category": "bank"}):
        assert client.get("/api/v1/services", params=params).status_code == 422, params
    response = client.get("/api/v1/services", params={"category": "bank"})
    assert "hospital, atm, shop, other" in response.json()["error"]["details"][0]["msg"]


def test_public_detail_404_and_422() -> None:
    client = make_client(FakeRepo())
    assert client.get(f"/api/v1/services/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/v1/services/not-a-uuid").status_code == 422


def test_admin_list_searches_by_name() -> None:
    client = make_client(FakeRepo())
    client.post("/api/v1/admin/services", json=BODY)
    client.post("/api/v1/admin/services", json={**BODY, "name": "City Hospital", "latitude": 1})
    body = client.get("/api/v1/admin/services", params={"search": "  hosp "}).json()
    assert [s["name"] for s in body["items"]] == ["City Hospital"]
    assert body["total"] == 1


def test_public_list_bbox_with_category() -> None:
    client = make_client(FakeRepo())
    client.post("/api/v1/admin/services", json=BODY)  # atm at (77.2, 28.6)
    client.post("/api/v1/admin/services", json={**BODY, "name": "Far ATM", "latitude": 10})
    client.post("/api/v1/admin/services", json={**BODY, "name": "Shop", "category": "shop"})
    body = client.get("/api/v1/services", params={"bbox": "77,28,78,29", "category": "atm"}).json()
    assert [s["name"] for s in body["items"]] == ["Corner ATM"]
    assert body["total"] == 1


def test_public_list_rejects_bad_bbox() -> None:
    client = make_client(FakeRepo())
    for bbox in (
        "179,0,-179,1",  # crosses the antimeridian
        "0,2,1,1",  # min_lat > max_lat
        "1,2,3",
        "a,b,c,d",
        "0,0,181,1",
        "0,-91,1,1",
        "nan,0,1,1",
    ):
        response = client.get("/api/v1/services", params={"bbox": bbox})
        assert response.status_code == 422, bbox
        assert response.json()["error"]["details"][0]["loc"][:2] == ["query", "bbox"]


def test_public_nearby_filters_and_orders() -> None:
    client = make_client(FakeRepo())
    client.post("/api/v1/admin/services", json={**BODY, "latitude": 28.61})
    client.post("/api/v1/admin/services", json={**BODY, "name": "Closer ATM"})
    client.post("/api/v1/admin/services", json={**BODY, "name": "Far ATM", "latitude": 30})
    client.post("/api/v1/admin/services", json={**BODY, "name": "Hosp", "category": "hospital"})
    params = {"lat": 28.6, "lng": 77.2, "radius_km": 5, "category": "atm"}
    response = client.get("/api/v1/services/nearby", params=params)
    assert response.status_code == 200
    body = response.json()
    assert [s["name"] for s in body["items"]] == ["Closer ATM", "Corner ATM"]
    assert (body["limit"], body["offset"], body["total"]) == (20, 0, 2)
    paged = client.get("/api/v1/services/nearby", params={**params, "limit": 1, "offset": 1})
    assert [s["name"] for s in paged.json()["items"]] == ["Corner ATM"]


def test_public_nearby_rejects_bad_params() -> None:
    client = make_client(FakeRepo())
    ok = {"lat": 28.6, "lng": 77.2}
    for params in (
        {"lng": 77.2},
        {"lat": 28.6},
        {**ok, "radius_km": 0},
        {**ok, "radius_km": -1},
        {**ok, "radius_km": 50.1},
        {**ok, "lat": 91},
        {**ok, "lng": "abc"},
        {**ok, "limit": 0},
        {**ok, "offset": -1},
        {**ok, "category": "bank"},
    ):
        assert client.get("/api/v1/services/nearby", params=params).status_code == 422, params
    assert client.get("/api/v1/services/nearby", params={**ok, "radius_km": 50}).status_code == 200
