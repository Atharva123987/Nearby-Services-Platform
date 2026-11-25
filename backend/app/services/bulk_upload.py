"""Parse a bulk-upload file (.csv or .json) into raw rows. Row validation happens elsewhere."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.core.errors import AppError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 10_000
REQUIRED_COLUMNS = ("name", "category", "latitude", "longitude")
OPTIONAL_COLUMNS = ("rating", "metadata")
_KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

# Browsers/OSes label CSV uploads inconsistently (Excel on Windows sends application/vnd.ms-excel).
_ALLOWED_TYPES = {
    "csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"},
    "json": {"application/json", "text/json", "text/plain"},
}
_GENERIC_TYPES = {"", "application/octet-stream"}


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnsupportedFileError(AppError):
    status_code = 415
    code = "unsupported_media_type"


class InvalidFileError(AppError):
    status_code = 422
    code = "invalid_file"


def file_format(filename: str | None, content_type: str | None) -> str:
    """Return "csv" or "json" from the extension; reject mismatched MIME types."""
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if ext not in _ALLOWED_TYPES:
        raise UnsupportedFileError("file must be .csv or .json")
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in _GENERIC_TYPES and mime not in _ALLOWED_TYPES[ext]:
        raise UnsupportedFileError(f"content type {mime!r} does not match a .{ext} file")
    return ext


def parse_upload(fmt: str, data: bytes) -> list[dict[str, Any]]:
    """Decode and parse; returns rows holding only known columns. Raises AppError subclasses."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError(f"file must be at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    if b"\x00" in data:
        raise InvalidFileError("file is not text")
    try:
        text = data.decode("utf-8-sig")  # strips the BOM Excel adds
    except UnicodeDecodeError as exc:
        raise InvalidFileError("file must be UTF-8 encoded") from exc
    if not text.strip():
        raise InvalidFileError("file is empty")

    rows = _parse_csv(text) if fmt == "csv" else _parse_json(text)
    if not rows:
        raise InvalidFileError("file has no data rows")
    if len(rows) > MAX_UPLOAD_ROWS:
        raise PayloadTooLargeError(f"file must have at most {MAX_UPLOAD_ROWS} rows")
    return rows


def _parse_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = [h.strip().lower() for h in next(reader)]
        _check_columns(header)
        rows = []
        for record in reader:
            if not any(cell.strip() for cell in record):
                continue  # blank line
            values = dict(zip(header, record, strict=False))
            rows.append({k: values.get(k, "") for k in _KNOWN_COLUMNS if k in header})
            if len(rows) > MAX_UPLOAD_ROWS:
                break
    except csv.Error as exc:
        raise InvalidFileError(f"malformed CSV: {exc}") from exc
    return rows


def _parse_json(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidFileError(f"malformed JSON: {exc.msg} (line {exc.lineno})") from exc
    if not isinstance(payload, list) or not all(isinstance(r, dict) for r in payload):
        raise InvalidFileError("JSON file must be an array of objects")
    rows = []
    for index, record in enumerate(payload):
        missing = [c for c in REQUIRED_COLUMNS if c not in record]
        if missing:
            raise InvalidFileError(
                f"row {index + 1} is missing required fields: {', '.join(missing)}"
            )
        rows.append({k: record[k] for k in _KNOWN_COLUMNS if k in record})
    return rows


def _check_columns(header: list[str]) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise InvalidFileError(f"missing required columns: {', '.join(missing)}")
