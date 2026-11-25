"""Error envelope and exception handlers.

Every error response has the shape::

    {"error": {"code": str, "message": str, "details": Any, "request_id": str | None}}
"""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import get_request_id

REQUEST_ID_HEADER = "X-Request-ID"


class AppError(Exception):
    """Base class for expected, client-facing errors raised by services."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


def error_body(
    code: str, message: str, details: Any = None, request_id: str | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id if request_id is not None else get_request_id(),
        }
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id()
    merged = dict(headers or {})
    if request_id:
        merged[REQUEST_ID_HEADER] = request_id
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(error_body(code, message, details, request_id)),
        headers=merged,
    )


def _code_for_status(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "error"


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    if isinstance(exc.detail, str):
        message, details = exc.detail, None
    else:
        message, details = HTTPStatus(exc.status_code).phrase, exc.detail
    return error_response(
        exc.status_code, _code_for_status(exc.status_code), message, details, exc.headers
    )


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    details = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors()
    ]
    return error_response(422, "validation_error", "Request validation failed", details)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    # Anything else is caught by RequestContextMiddleware (the last-resort 500 handler).
