"""Create the database if missing, then any missing tables. Safe to re-run.

create_all never alters existing tables: after a column change, drop the
database, restart the backend and re-run dealdata.load.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import models  # noqa: F401  registers tables on Base.metadata
from app.config import get_settings
from app.db import Base, get_engine


def ensure_database() -> None:
    url = make_url(get_settings().DATABASE_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


def init_db() -> None:
    ensure_database()
    Base.metadata.create_all(get_engine())
