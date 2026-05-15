from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request, status
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import constant_time_compare
from app.db.session import get_db_session


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(settings: Settings = Depends(get_settings)) -> Generator[Session, None, None]:
    yield from get_db_session(settings)


def require_internal_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    if settings.internal_api_key is None:
        raise AppError(status.HTTP_503_SERVICE_UNAVAILABLE, "internal_api_key_missing", "Internal API key is not configured")
    if x_api_key is None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "missing_api_key", "X-API-Key header is required")
    expected = settings.internal_api_key.get_secret_value()
    if not constant_time_compare(x_api_key, expected):
        raise AppError(status.HTTP_401_UNAUTHORIZED, "invalid_api_key", "Invalid internal API key")
