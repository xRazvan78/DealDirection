"""run_sql_scripts(): the coin shop's partner shops and gift cards, from data/sql/*.sql."""

from decimal import Decimal

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dealdata.run_sql import SQL_DIR, run_sql_scripts

SHOPS = {"Decathlon", "Delfino", "SuperBob"}
CARDS = {(Decimal("50.00"), 5000), (Decimal("100.00"), 10000), (Decimal("150.00"), 15000)}


def _cards_by_shop(conn: Connection) -> dict[str, set[tuple[Decimal, int]]]:
    rows = conn.execute(text(
        "SELECT s.name, g.value_lei, g.cost_points FROM partner_gift_cards g "
        "JOIN partner_shops s ON s.id = g.shop_id WHERE g.active"
    ))
    found: dict[str, set[tuple[Decimal, int]]] = {}
    for name, value, cost in rows:
        found.setdefault(name, set()).add((value, cost))
    return found


def _counts(conn: Connection) -> tuple[int, int]:
    return (
        conn.scalar(text("SELECT count(*) FROM partner_shops")),
        conn.scalar(text("SELECT count(*) FROM partner_gift_cards")),
    )


@pytest.fixture
def fresh(db: Session) -> Connection:
    """A connection on an empty schema, so the scripts create the tables themselves."""
    conn = db.connection()
    conn.execute(text("CREATE SCHEMA partner_sql_test"))
    conn.execute(text("SET LOCAL search_path TO partner_sql_test"))
    return conn


def test_scripts_are_found_in_order() -> None:
    names = [path.name for path in sorted(SQL_DIR.glob("*.sql"))]
    assert names[:2] == ["01_partner_shops_schema.sql", "02_partner_shops_seed.sql"]


def test_scripts_create_the_tables_and_every_gift_card(fresh: Connection) -> None:
    run_sql_scripts(fresh)

    cards = _cards_by_shop(fresh)
    assert set(cards) == SHOPS
    assert all(found == CARDS for found in cards.values())
    names = {row[0] for row in fresh.execute(text("SELECT name FROM partner_gift_cards"))}
    assert "Card cadou Decathlon 50 lei" in names


def test_running_again_adds_no_duplicates(fresh: Connection) -> None:
    run_sql_scripts(fresh)
    first = _counts(fresh)
    run_sql_scripts(fresh)
    assert _counts(fresh) == first == (3, 9)


def test_running_again_restores_a_changed_cost(fresh: Connection) -> None:
    run_sql_scripts(fresh)
    fresh.execute(text("UPDATE partner_gift_cards SET cost_points = 1, active = false"))
    run_sql_scripts(fresh)
    assert all(found == CARDS for found in _cards_by_shop(fresh).values())


@pytest.mark.parametrize("cost", [0, -100])
def test_a_cost_that_is_not_positive_is_refused(fresh: Connection, cost: int) -> None:
    run_sql_scripts(fresh)
    with pytest.raises(IntegrityError), fresh.begin_nested():
        fresh.execute(text(
            "INSERT INTO partner_gift_cards (shop_id, name, value_lei, cost_points) "
            "SELECT id, 'Card test', 75, :cost FROM partner_shops WHERE name = 'Decathlon'"
        ), {"cost": cost})


def test_the_same_value_twice_in_one_shop_is_refused(fresh: Connection) -> None:
    run_sql_scripts(fresh)
    with pytest.raises(IntegrityError), fresh.begin_nested():
        fresh.execute(text(
            "INSERT INTO partner_gift_cards (shop_id, name, value_lei, cost_points) "
            "SELECT id, 'Card dublat', 50, 5000 FROM partner_shops WHERE name = 'Delfino'"
        ))


def test_scripts_work_on_the_real_tables_too(db: Session) -> None:
    """The models create the same tables, so the scripts must run on top of them."""
    conn = db.connection()
    run_sql_scripts(conn)
    assert SHOPS <= set(_cards_by_shop(conn))
