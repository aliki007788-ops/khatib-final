"""
Database engine, session management.
Production migrations are handled EXCLUSIVELY via Alembic.
`Base.metadata.create_all()` is only used for local/dev quick start,
never as the production migration mechanism.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    url = settings.database_url
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if settings.is_production:
            raise RuntimeError(
                "SQLite must not be used as the production database. "
                "Set DATABASE_URL to a PostgreSQL connection string."
            )
    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )


engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Use outside FastAPI request context (worker, scripts, scheduler)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db_dev_only() -> None:
    """
    Creates tables directly from models.
    ONLY for local development bootstrap / quick prototyping.
    Production databases MUST be provisioned via Alembic migrations.
    """
    if settings.is_production:
        raise RuntimeError(
            "init_db_dev_only() must never run in production. Use Alembic."
        )
    from app.core import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
