from __future__ import annotations

from sqlalchemy import text

from app.core.db import engine
from app.core.config import settings


def check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_redis() -> bool:
    try:
        import redis
        client = redis.from_url(settings.redis_url, socket_connect_timeout=1)
        return bool(client.ping())
    except Exception:
        return False


def readiness_status() -> dict:
    database_ok = check_database()
    redis_ok = check_redis()

    ready = database_ok

    if settings.redis_required:
        ready = ready and redis_ok

    return {
        "status": "ready" if ready else "not_ready",
        "database": database_ok,
        "redis": redis_ok,
        "environment": settings.environment,
        "version": settings.app_version,
    }
