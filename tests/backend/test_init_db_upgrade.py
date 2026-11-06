"""init_db's upgrade of an outdated, empty table. Postgres rolls DDL back, so nothing is left behind."""

from sqlalchemy import inspect, text

from app.db import get_engine
from app.init_db import drop_if_outdated_and_empty


def test_outdated_empty_table_is_dropped() -> None:
    with get_engine().connect() as conn, conn.begin() as tx:
        conn.execute(text("CREATE TABLE upgrade_probe (id int, store_id int)"))

        assert drop_if_outdated_and_empty(conn, "upgrade_probe", "brand") is True
        assert not inspect(conn).has_table("upgrade_probe")
        tx.rollback()


def test_outdated_table_with_rows_is_kept() -> None:
    with get_engine().connect() as conn, conn.begin() as tx:
        conn.execute(text("CREATE TABLE upgrade_probe (id int, store_id int)"))
        conn.execute(text("INSERT INTO upgrade_probe VALUES (1, 1)"))

        assert drop_if_outdated_and_empty(conn, "upgrade_probe", "brand") is False
        assert inspect(conn).has_table("upgrade_probe")
        tx.rollback()


def test_current_table_is_kept() -> None:
    with get_engine().connect() as conn, conn.begin() as tx:
        conn.execute(text("CREATE TABLE upgrade_probe (id int, brand text)"))

        assert drop_if_outdated_and_empty(conn, "upgrade_probe", "brand") is False
        tx.rollback()


def test_missing_table_is_fine() -> None:
    with get_engine().connect() as conn:
        assert drop_if_outdated_and_empty(conn, "no_such_table_here", "brand") is False


def test_loyalty_cards_has_the_new_columns_after_init() -> None:
    columns = {c["name"] for c in inspect(get_engine()).get_columns("loyalty_cards")}

    assert {"brand", "code_text", "code_format", "photo"} <= columns
    assert "store_id" not in columns
