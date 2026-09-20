"""
Application entrypoint — Full Khatib application (production candidate).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.core.logging import configure_logging
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.core.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION

from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import billing as billing_router
from app.routers import chat as chat_router
from app.routers import eitaa as eitaa_router
from app.routers import health as health_router
from app.routers import learning as learning_router
from app.routers import privacy as privacy_router
from app.routers import progress as progress_router
from app.routers import speech as speech_router
from app.routers import translate as translate_router

logger = logging.getLogger("khatib")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.debug)
    logger.info("application_starting", extra={"request_id": "-"})
    yield
    logger.info("application_stopping", extra={"request_id": "-"})


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    if settings.allowed_hosts_list:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts_list,
        )

    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        path = request.url.path
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=path,
            status=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            method=request.method,
            path=path,
        ).observe(duration)
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={"detail": "خطای داخلی سرور رخ داد."},
        )

    # All routers
    app.include_router(health_router.router)
    app.include_router(auth_router.router)
    app.include_router(billing_router.router)
    app.include_router(speech_router.router)
    app.include_router(chat_router.router)
    app.include_router(progress_router.router)
    app.include_router(learning_router.router)
    app.include_router(admin_router.router)
    app.include_router(privacy_router.router)
    app.include_router(eitaa_router.router)
    app.include_router(translate_router.router)

    @app.get("/metrics")
    def metrics():
        if settings.is_production and not settings.metrics_enabled:
            return Response(status_code=404)
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app = create_app()
