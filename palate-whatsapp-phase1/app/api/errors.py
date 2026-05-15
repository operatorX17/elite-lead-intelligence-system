from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def _error_payload(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            },
            "request_id": getattr(request.state, "request_id", None),
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _error_payload(request, exc.status_code, exc.code, exc.message)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return _error_payload(request, exc.status_code, "http_error", detail)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_payload(request, 422, "validation_error", str(exc.errors()))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled application error",
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return _error_payload(request, 500, "internal_server_error", "Unexpected server error")
