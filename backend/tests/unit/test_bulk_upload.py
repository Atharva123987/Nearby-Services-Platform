import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from app.core.errors import AppError
from app.services.bulk_upload import MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS, file_format, parse_upload
from app.services.service_service import ServiceService
from tests.unit.test_admin_services import make_client
from tests.unit.test_cache import FakeRedis
from tests.unit.test_service_service import FakeRepo

URL = "/api/v1/admin/services/bulk"
HEADER = "name,category,latitude,longitude"


def test_csv_with_bom_quotes_unicode_and_extra_columns() -> None:
    text = (
        "﻿Name, Category ,latitude,longitude,notes\n"
        '"Shah, Sons ""ATM""",atm,18.5,73.8,ignored\n'
        "\n"
        "पुणे दवाखाना,hospital,18.52,73.85,x\n"
    )
    rows = parse_upload("csv", text.encode("utf-8"))
    assert rows == [
        {"name": 'Shah, Sons "ATM"', "category": "atm", "latitude": "18.5", "longitude": "73.8"},
        {"name": "पुणे दवाखाना", "category": "hospital", "latitude": "18.52", "longitude": "73.85"},
    ]


def test_json_keeps_known_fields() -> None:
    data = [{"name": "राम", "category": "atm", "latitude": 1, "longitude": 2, "x": 1, "rating": 4}]
    rows = parse_upload("json", json.dumps(data, ensure_ascii=False).encode())
    assert rows == [{"name": "राम", "category": "atm", "latitude": 1, "longitude": 2, "rating": 4}]


@pytest.mark.parametrize(
    ("fmt", "data", "status"),
    [
        ("csv", b"", 422),
        ("csv", b"  \n", 422),
        ("csv", HEADER.encode() + b"\n", 422),  # header only
        ("csv", b"name,category\nA,atm\n", 422),  # missing columns
        ("csv", (HEADER + ',notes\nA,atm,1,2,"incomplete').encode(), 422),
        ("csv", b"\x89PNG\r\n\x1a\n\x00\x00", 422),  # binary
        ("csv", b"\xff\xfe\xfa", 422),  # not UTF-8
        ("json", b"{not json", 422),
        ("json", b'{"name": "a"}', 422),  # not an array
        ("json", b"[]", 422),
        ("csv", b"a" * (MAX_UPLOAD_BYTES + 1), 413),
        ("csv", (HEADER + "\n" + "A,atm,1,2\n" * (MAX_UPLOAD_ROWS + 1)).encode(), 413),
    ],
)
def test_parse_errors(fmt: str, data: bytes, status: int) -> None:
    with pytest.raises(AppError) as exc:
        parse_upload(fmt, data)
    assert exc.value.status_code == status


def test_file_format() -> None:
    assert file_format("a.CSV", "application/vnd.ms-excel") == "csv"
    assert file_format("a.json", "application/octet-stream") == "json"
    for name, mime in (("a.xlsx", "text/csv"), ("csv", None), ("a.csv", "image/png")):
        with pytest.raises(AppError) as exc:
            file_format(name, mime)
        assert exc.value.status_code == 415


def test_bulk_endpoint() -> None:
    repo = FakeRepo()
    client = make_client(repo)
    csv_text = f'{HEADER},metadata\nA,atm,1,2,"{{""open"": true}}"\nB,atm,95,2,\n'
    ok = client.post(URL, files={"file": ("s.csv", csv_text, "text/csv")})
    assert ok.status_code == 200
    body = ok.json()
    assert (body["total"], body["inserted"], body["failed"]) == (2, 1, 1)
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["field"] == "latitude"
    assert next(iter(repo.items.values())).metadata == {"open": True}

    wrong = client.post(URL, files={"file": ("s.txt", "x", "text/plain")})
    assert wrong.status_code == 415
    assert wrong.json()["error"]["code"] == "unsupported_media_type"

    assert client.post(URL).status_code == 422  # no file


GOOD: dict[str, Any] = {"name": "A", "category": "atm", "latitude": "1", "longitude": "2"}


@pytest.mark.parametrize(("mode", "inserted"), [("strict", 0), ("partial", 1)])
def test_bulk_json_reports_missing_fields_by_row(mode: str, inserted: int) -> None:
    repo = FakeRepo()
    client = make_client(repo)
    incomplete = {key: value for key, value in GOOD.items() if key != "longitude"}
    response = client.post(
        URL,
        params={"mode": mode},
        files={"file": ("services.json", json.dumps([GOOD, incomplete]), "application/json")},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["inserted"], body["failed"]) == (2, inserted, 1)
    assert [(error["row"], error["field"]) for error in body["errors"]] == [(2, "longitude")]
    assert len(repo.items) == inserted


def run_bulk(rows: list[dict[str, Any]], mode: str = "partial") -> tuple[Any, FakeRepo, FakeRedis]:
    repo, redis = FakeRepo(), FakeRedis()
    service = ServiceService(repo, cache=redis)  # type: ignore[arg-type]
    return asyncio.run(service.bulk_create(rows, mode)), repo, redis  # type: ignore[arg-type]


def test_partial_inserts_valid_rows_and_reports_errors() -> None:
    rows = [
        GOOD,
        {**GOOD, "name": "a"},  # duplicate of row 1 (case-insensitive)
        {**GOOD, "name": "B", "latitude": "120", "longitude": "10"},  # swapped
        {**GOOD, "name": "C", "metadata": "{bad"},
        {**GOOD, "name": "D", "metadata": '{"x": 1}', "rating": ""},
    ]
    result, repo, redis = run_bulk(rows)
    assert (result.total, result.inserted, result.failed) == (5, 2, 3)
    assert [(e.row, e.field) for e in result.errors] == [
        (2, None),
        (3, "latitude"),
        (4, "metadata"),
    ]
    assert "swapped" in result.errors[1].message
    assert repo.commits == 1
    assert redis.store.get("services:version") == "1"  # bumped once


def test_strict_inserts_nothing_on_error() -> None:
    result, repo, _ = run_bulk([GOOD, {**GOOD, "name": ""}], mode="strict")
    assert (result.inserted, result.failed) == (0, 1)
    assert repo.items == {} and repo.commits == 0

    result, repo, _ = run_bulk([GOOD], mode="strict")
    assert result.inserted == 1 and repo.commits == 1


DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@pytest.mark.parametrize("name", ["sample_services.csv", "sample_services.json"])
def test_sample_files_load_in_strict_mode(name: str) -> None:
    path = DATA_DIR / name
    rows = parse_upload(file_format(path.name, None), path.read_bytes())
    result, _, _ = run_bulk(rows, mode="strict")
    assert result.errors == []
    assert result.inserted == result.total >= 500
    categories = {r["category"] for r in rows}
    assert categories == {"hospital", "atm", "shop", "other"}
    assert any(r.get("rating") in ("", None) for r in rows)
    assert any(r.get("metadata") in ("", None) for r in rows)


def test_template_downloads_and_parses() -> None:
    response = make_client(FakeRepo()).get(f"{URL}/template")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    result, _, _ = run_bulk(parse_upload("csv", response.content), mode="strict")
    assert (result.inserted, result.errors) == (1, [])
