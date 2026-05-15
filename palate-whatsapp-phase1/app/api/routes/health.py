from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_settings
from app.core.config import Settings
from app.db.session import check_database
from app.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="palate-whatsapp-phase1",
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/ready", response_model=ReadyResponse)
def ready(response: Response, settings: Settings = Depends(get_settings)) -> ReadyResponse:
    missing = settings.missing_required_settings()
    checks: dict[str, object] = {
        "missing_settings": missing,
        "database": "unknown",
    }
    ready_state = not missing

    if settings.database_url:
        try:
            check_database(settings)
            checks["database"] = "ok"
        except Exception as exc:
            ready_state = False
            checks["database"] = f"error:{exc}"
    else:
        ready_state = False
        checks["database"] = "missing"

    if not ready_state:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ready" if ready_state else "not_ready",
        ready=ready_state,
        checks=checks,
    )
