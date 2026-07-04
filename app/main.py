import hashlib
import os
import platform
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import collection, competitors, data, health, metrics
from app.api.middleware import RateLimitMiddleware, TracingMiddleware
from app.configuration.settings import Settings, get_settings
from app.database.connection import db_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    logger = structlog.get_logger("startup")
    api_key_hash = (
        hashlib.sha256(settings.api_key.encode()).hexdigest()[:16] if settings.api_key else "none"
    )
    logger.info(
        "application_startup",
        pid=os.getpid(),
        python=platform.python_version(),
        env=settings.environment,
        debug=settings.debug,
        api_key_hash=f"{api_key_hash}...",
        api_key_length=len(settings.api_key) if settings.api_key else 0,
        working_directory=str(Path.cwd()),
        env_file_exists=Path(".env").exists(),
        database_url=settings.database.url.split("@")[-1]
        if "@" in settings.database.url
        else settings.database.url,
    )

    from app.collectors.fetcher import PlaywrightRenderer

    browser_ok, browser_msg = await PlaywrightRenderer.verify_browser()
    if browser_ok:
        logger.info("playwright_browser_verified", message=browser_msg)
    else:
        logger.error(
            "playwright_browser_missing",
            message=browser_msg,
            hint="Application will continue but JS-rendered pages will fail",
        )

    await db_manager.connect()
    await db_manager.create_tables()

    from app.services.config_sync_service import config_sync_service

    await config_sync_service.sync_competitors()

    from app.schedulers.scheduler import scheduler

    await scheduler.start()

    logger.info("application_ready", playwright_available=browser_ok)

    yield

    await scheduler.stop()
    await db_manager.disconnect()
    logger.info("application_shutdown")


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
        openapi_tags=[
            {"name": "health", "description": "Health and status endpoints"},
            {"name": "competitors", "description": "Competitor management"},
            {"name": "collection", "description": "Data collection operations"},
            {"name": "metrics", "description": "System metrics"},
            {"name": "data", "description": "Data query endpoints"},
        ],
    )

    app.openapi_schema = app.openapi()
    if app.openapi_schema:
        app.openapi_schema["components"] = app.openapi_schema.get("components", {})
        app.openapi_schema["components"]["securitySchemes"] = {
            "ApiKeyHeader": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for authentication. Pass the X-API-Key header.",
            }
        }
        app.openapi_schema["security"] = [{"ApiKeyHeader": []}]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=settings.debug,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
    app.add_middleware(TracingMiddleware)

    app.include_router(health.router)
    app.include_router(competitors.router)
    app.include_router(collection.router)
    app.include_router(metrics.router)
    app.include_router(data.router)

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
