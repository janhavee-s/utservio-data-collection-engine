from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import collection, competitors, health, metrics
from app.api.middleware import RateLimitMiddleware
from app.configuration.settings import Settings, get_settings
from app.database.connection import db_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await db_manager.connect()
    await db_manager.create_tables()

    from app.services.config_sync_service import config_sync_service

    await config_sync_service.sync_competitors()

    from app.schedulers.scheduler import scheduler

    await scheduler.start()

    yield

    await scheduler.stop()
    await db_manager.disconnect()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Utservio Competitor Intelligence Engine",
        description="Data collection engine for competitor intelligence",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=settings.debug,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    app.include_router(health.router)
    app.include_router(competitors.router)
    app.include_router(collection.router)
    app.include_router(metrics.router)

    _configure_logging(settings.log_level)

    return app


def _configure_logging(log_level: str) -> None:
    import logging

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


app = create_app()
