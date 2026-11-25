import json

import pytest

from app.core.errors import AppError
from app.services.bulk_upload import MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS, file_format, parse_upload
from tests.unit.test_admin_services import make_client
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
        ("csv", b"\x89PNG\r\n\x1a\n\x00\x00", 422),  # binary
        ("csv", b"\xff\xfe\xfa", 422),  # not UTF-8
        ("json", b"{not json", 422),
        ("json", b'{"name": "a"}', 422),  # not an array
        ("json", b"[]", 422),
        ("json", b'[{"name": "a", "category": "atm"}]', 422),  # missing fields
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
    client = make_client(FakeRepo())
    ok = client.post(URL, files={"file": ("s.csv", f"{HEADER}\nA,atm,1,2\n", "text/csv")})
    assert ok.status_code == 200
    assert ok.json()["total"] == 1

    wrong = client.post(URL, files={"file": ("s.txt", "x", "text/plain")})
    assert wrong.status_code == 415
    assert wrong.json()["error"]["code"] == "unsupported_media_type"

    assert client.post(URL).status_code == 422  # no file
