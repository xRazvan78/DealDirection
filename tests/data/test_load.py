import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Store, StoreLocation, StoreProduct, User, UserStore
from dealdata.load import load_snapshot
from dealdata.normalize import Size
from dealdata.tree import LeafRule, load_tree

DATA = Path(__file__).parents[2] / "data"
STORES = {
    "Magazin Load A": {
        "colour": "#d6001c",
        "locations": [{"address": "Strada Test 1", "latitude": 45.1, "longitude": 25.2}],
    },
    "Magazin Load B": {"colour": "#004e9f", "locations": []},
}
RULES = [
    LeafRule(
        ("Lapte Load", "3.5%", "1 l"),
        ("lapte",),
        (),
        Size(Decimal("1.000"), "l"),
        ("lapte", "lapte integral"),
        group="Grupa Load",
    ),
    LeafRule(
        ("Lapte Load", "1.5%", "1 l"),
        ("lapte",),
        (),
        Size(Decimal("1.000"), "l"),
        (),
        group="Grupa Load",
    ),
]
MILK_PATH = ["Grupa Load", "Lapte Load", "3.5%", "1 l"]


def snapshot_item(**changes: object) -> dict:
    item = {
        "store": "Magazin Load A",
        "name": "Lapte Brânză Load, 1 l",
        "brand": "Marca",
        "price": "8.50",
        "unit": "l",
        "source_url": "https://example.com/lapte",
        "path": MILK_PATH,
        "updated_at": "2026-11-06",
    }
    return {**item, **changes}


def category(db: Session, name: str) -> Category:
    return db.scalars(select(Category).where(Category.name == name)).one()


def product(db: Session, name: str = "Lapte Brânză Load, 1 l") -> StoreProduct:
    return db.scalars(select(StoreProduct).where(StoreProduct.name == name)).one()


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_load_snapshot_builds_the_category_chain(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)

    group = category(db, "Grupa Load")
    milk = category(db, "Lapte Load")
    fat = db.scalars(
        select(Category).where(Category.name == "3.5%", Category.parent_id == milk.id)
    ).one()
    size = db.scalars(select(Category).where(Category.parent_id == fat.id)).one()

    assert (group.parent_id, group.level) == (None, "category")
    assert (milk.parent_id, milk.level) == (group.id, "category")
    assert fat.level == "type"
    assert (size.name, size.level) == ("1 l", "size")
    assert (size.size_amount, size.size_unit) == (Decimal("1.000"), "l")
    assert size.aliases == ["lapte", "lapte integral"]


def test_load_snapshot_leaves_out_categories_with_no_products(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)

    milk = category(db, "Lapte Load")
    types = db.scalars(select(Category.name).where(Category.parent_id == milk.id)).all()

    assert types == ["3.5%"]


def test_load_snapshot_saves_a_product(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)

    saved = product(db)
    milk = category(db, "Lapte Load")
    fat = db.scalars(select(Category).where(Category.parent_id == milk.id)).one()
    size = db.scalars(select(Category).where(Category.parent_id == fat.id)).one()
    store = db.scalars(select(Store).where(Store.name == "Magazin Load A")).one()

    assert saved.store_id == store.id
    assert saved.size_category_id == size.id
    assert saved.type_category_id == fat.id
    assert saved.brand == "Marca"
    assert saved.price == Decimal("8.50")
    assert saved.unit == "l"
    assert saved.source_url == "https://example.com/lapte"
    assert saved.image_url is None
    assert saved.barcode is None


def test_load_snapshot_folds_name_and_brand_for_search(db: Session) -> None:
    load_snapshot(db, [snapshot_item(brand="Țară")], STORES, RULES)

    assert product(db).search_text == "lapte branza load, 1 l tara"


def test_load_snapshot_searches_by_name_when_there_is_no_brand(db: Session) -> None:
    load_snapshot(db, [snapshot_item(brand=None)], STORES, RULES)

    assert product(db).search_text == "lapte branza load, 1 l"


def test_load_snapshot_dates_products_from_the_scrape(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)

    assert product(db).updated_at == datetime(2026, 11, 6, tzinfo=UTC)


def test_load_snapshot_saves_stores_and_locations(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)

    store = db.scalars(select(Store).where(Store.name == "Magazin Load A")).one()
    location = db.scalars(select(StoreLocation).where(StoreLocation.store_id == store.id)).one()

    assert store.colour == "#d6001c"
    assert (location.address, location.latitude, location.longitude) == (
        "Strada Test 1",
        45.1,
        25.2,
    )


def test_load_snapshot_creates_a_demo_user_with_every_store_selected(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)

    demo = db.scalars(select(User).where(User.is_demo)).one()
    selected = db.scalars(
        select(Store.name).join(UserStore, UserStore.store_id == Store.id).where(
            UserStore.user_id == demo.id
        )
    ).all()

    assert set(STORES) <= set(selected)
    assert demo.password_hash.startswith("$2")


def test_loading_twice_adds_no_rows(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)
    models = (Category, Store, StoreLocation, StoreProduct, User, UserStore)
    before = [count(db, model) for model in models]

    load_snapshot(db, [snapshot_item()], STORES, RULES)

    assert [count(db, model) for model in models] == before


def test_loading_again_updates_the_price_and_keeps_the_id(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)
    first_id = product(db).id

    load_snapshot(db, [snapshot_item(price="9.99", updated_at="2026-11-07")], STORES, RULES)

    saved = product(db)
    assert saved.id == first_id
    assert saved.price == Decimal("9.99")
    assert saved.updated_at == datetime(2026, 11, 7, tzinfo=UTC)


def test_loading_again_keeps_the_demo_users_password(db: Session) -> None:
    load_snapshot(db, [snapshot_item()], STORES, RULES)
    first_hash = db.scalars(select(User.password_hash).where(User.is_demo)).one()

    load_snapshot(db, [snapshot_item()], STORES, RULES)

    assert db.scalars(select(User.password_hash).where(User.is_demo)).one() == first_hash


def test_load_snapshot_rejects_a_product_whose_store_is_unknown(db: Session) -> None:
    with pytest.raises(KeyError, match="Magazin Necunoscut"):
        load_snapshot(db, [snapshot_item(store="Magazin Necunoscut")], STORES, RULES)


def test_load_snapshot_rejects_a_path_missing_from_the_tree(db: Session) -> None:
    item = snapshot_item(path=["Grupa Load", "Lapte Load", "9%", "1 l"])

    with pytest.raises(KeyError, match="9%"):
        load_snapshot(db, [item], STORES, RULES)


def test_real_data_loads(db: Session) -> None:
    products = json.loads((DATA / "snapshot" / "products.json").read_text(encoding="utf-8"))
    stores = yaml.safe_load((DATA / "stores.yaml").read_text(encoding="utf-8"))["stores"]

    load_snapshot(db, products, stores, load_tree(DATA / "tree.yaml"))

    saved = db.scalar(
        select(func.count())
        .select_from(StoreProduct)
        .join(Store, Store.id == StoreProduct.store_id)
        .where(Store.name.in_(stores))
    )
    assert saved == len(products)
