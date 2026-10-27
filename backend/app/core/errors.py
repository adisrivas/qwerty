"""Application errors and their HTTP representation (RFC 9457 problem details)."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_CONTENT_TYPE = "application/problem+json"


class AppError(Exception):
    """Base class for errors that map to a problem-details response."""

    status_code: int = HTTPStatus.BAD_REQUEST
    title: str = "Bad request"

    def __init__(self, detail: str, **extra: Any) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class OutOfScopeError(AppError):
    """The request asks for a date outside the supported window."""

    status_code = HTTPStatus.BAD_REQUEST
    title = "Date out of supported scope"


class NotFoundError(AppError):
    """A requested resource does not exist."""

    status_code = HTTPStatus.NOT_FOUND
    title = "Not found"


class DataUnavailableError(AppError):
    """The data snapshot could not be loaded, so the service cannot answer."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    title = "Data unavailable"


class SnapshotIntegrityError(RuntimeError):
    """Raised when a snapshot file does not match its manifest."""


def _problem(status: int, title: str, detail: str, request: Request, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": str(request.url.path),
        **extra,
    }
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_CONTENT_TYPE)


def register_error_handlers(app: FastAPI) -> None:
    """Attach handlers so every error leaves the API in the same shape."""

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _problem(exc.status_code, exc.title, exc.detail, request, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = {
            ".".join(
                str(part) for part in err["loc"] if part not in ("query", "path", "body")
            ): err["msg"]
            for err in exc.errors()
        }
        return _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "One or more validation errors occurred.",
            "Check the listed parameters.",
            request,
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem(exc.status_code, "HTTP error", str(exc.detail), request)
