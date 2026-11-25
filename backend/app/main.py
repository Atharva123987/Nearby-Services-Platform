"""App factory: middleware, exception handlers, routers, lifespan."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.api.v1 import api_router
from app.cache.redis import create_redis
from app.core.config import Settings, get_settings
from app.core.errors import REQUEST_ID_HEADER, register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory
from app.middleware.request_context import RequestContextMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level.value)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.redis = create_redis(settings)
        logger.info("startup", extra={"app_env": settings.app_env.value})
        try:
            yield
        finally:
            await app.state.redis.aclose()
            await engine.dispose()
            logger.info("shutdown")

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None if settings.is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_prod else "/openapi.json",
    )

    # Dependencies (SettingsDep) must see the same settings this app was built with.
    app.dependency_overrides[get_settings] = lambda: settings
    register_exception_handlers(app)

    # Added last => outermost: every response (CORS rejections included) gets a request ID.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware, expose_errors=not settings.is_prod)

    app.include_router(health.router)
    app.include_router(api_router)
    return app


app = create_app()
