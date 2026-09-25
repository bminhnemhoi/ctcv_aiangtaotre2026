"""SQLAlchemy engine, session factory and the per-request session dependency."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

SQLITE_PREFIX = "sqlite"
SQLITE_MEMORY_SUFFIXES = ("sqlite://", "sqlite+pysqlite://")
SQLITE_MEMORY_MARKER = ":memory:"


def _is_memory_sqlite(url: str) -> bool:
    return url.endswith(SQLITE_MEMORY_SUFFIXES) or SQLITE_MEMORY_MARKER in url


def make_engine(database_url: str) -> Engine:
    """Create an engine; SQLite gets thread-safe connect args and a static pool for memory DBs."""
    if not database_url.startswith(SQLITE_PREFIX):
        return create_engine(database_url, pool_pre_ping=True)
    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if _is_memory_sqlite(database_url):
        kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to ``engine``."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def ping(engine: Engine) -> bool:
    """Return True when ``SELECT 1`` succeeds on ``engine``."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency yielding one session per request from ``app.state.session_factory``."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
