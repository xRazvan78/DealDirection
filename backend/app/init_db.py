"""Create the database if missing, then any missing tables. Safe to re-run.

create_all never alters existing tables: after a column change, drop the
database, restart the backend and re-run dealdata.load. The one exception is
handled here: a table whose old version could never hold rows is replaced
automatically when it's still empty, so nobody has to rebuild their database.
"""

from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.engine import make_url

from app import models  # noqa: F401  registers tables on Base.metadata
from app.config import get_settings
from app.db import Base, get_engine

# Tables that changed shape, and a column only the new version has.
# loyalty_cards: store_id and a photo became brand and a decoded code.
_UPGRADES = {"loyalty_cards": "brand"}


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


def drop_if_outdated_and_empty(conn: Connection, table: str, new_column: str) -> bool:
    """Drop `table` if it lacks `new_column` and has no rows, so create_all rebuilds it.

    A table with rows is never touched. Returns whether the table was dropped.
    """
    inspector = inspect(conn)
    if not inspector.has_table(table):
        return False
    if new_column in {column["name"] for column in inspector.get_columns(table)}:
        return False
    if conn.scalar(text(f'SELECT EXISTS (SELECT 1 FROM "{table}")')):
        return False
    conn.execute(text(f'DROP TABLE "{table}"'))
    return True


def init_db() -> None:
    ensure_database()
    engine = get_engine()
    with engine.begin() as conn:
        for table, new_column in _UPGRADES.items():
            drop_if_outdated_and_empty(conn, table, new_column)
    Base.metadata.create_all(engine)
