from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import (
    RequestIdMiddleware,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.routes.captain import router as captain_router
from app.api.routes.demo import router as demo_router
from app.api.routes.health import router as health_router
from app.api.routes.intake import router as intake_router
from app.api.routes.orders import router as orders_router
from app.api.routes.tracking import router as tracking_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.whatsapp import router as whatsapp_router
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(runtime_settings.log_level)
        logger.info("Starting Palate WhatsApp Phase 1 backend")
        yield
        logger.info("Stopping Palate WhatsApp Phase 1 backend")

    app = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings

    app.add_middleware(RequestIdMiddleware)
    if runtime_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=runtime_settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.include_router(health_router)
    app.include_router(webhooks_router)
    app.include_router(whatsapp_router)
    app.include_router(orders_router)
    app.include_router(captain_router)
    app.include_router(demo_router)
    app.include_router(intake_router)
    app.include_router(tracking_router)

    return app


app = create_app()
