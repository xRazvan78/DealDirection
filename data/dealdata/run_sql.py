"""Entry point: uv run python -m dealdata.run_sql. Re-runnable.

Runs every data/sql/*.sql file in name order, in one transaction: the coin
shop's partner shops (Decathlon, Delfino, SuperBob) and their gift cards.
The files also work on their own with psql -f.
"""

from pathlib import Path

from app.db import get_engine
from app.init_db import ensure_database
from sqlalchemy import Connection

SQL_DIR = Path(__file__).parents[1] / "sql"


def run_sql_scripts(conn: Connection) -> list[str]:
    """Run each script on conn and return their names. The caller commits."""
    scripts = sorted(SQL_DIR.glob("*.sql"))
    for path in scripts:
        conn.exec_driver_sql(path.read_text(encoding="utf-8"))
    return [path.name for path in scripts]


def main() -> None:
    ensure_database()
    with get_engine().begin() as conn:
        names = run_sql_scripts(conn)
    print(f"Ran {len(names)} SQL scripts: {', '.join(names)}")


if __name__ == "__main__":
    main()
