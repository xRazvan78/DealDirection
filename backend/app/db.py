"""Database engine, session and declarative base."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Parent class for every model in app.models."""


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().DATABASE_URL)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that gives one session per request."""
    session = sessionmaker(bind=get_engine(), expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
