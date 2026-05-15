from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.urls import normalize_database_url

_ENGINE_CACHE: dict[str, Engine] = {}
_SESSIONMAKER_CACHE: dict[str, sessionmaker[Session]] = {}


def get_engine(settings: Settings) -> Engine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    database_url = normalize_database_url(settings.database_url)

    cached = _ENGINE_CACHE.get(database_url)
    if cached is not None:
        return cached

    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )
    _ENGINE_CACHE[database_url] = engine
    return engine


def get_session_factory(settings: Settings) -> sessionmaker[Session]:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    database_url = normalize_database_url(settings.database_url)

    cached = _SESSIONMAKER_CACHE.get(database_url)
    if cached is not None:
        return cached

    factory = sessionmaker(
        bind=get_engine(settings),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    _SESSIONMAKER_CACHE[database_url] = factory
    return factory


def get_db_session(settings: Settings) -> Iterator[Session]:
    session_factory = get_session_factory(settings)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def check_database(settings: Settings) -> None:
    engine = get_engine(settings)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
