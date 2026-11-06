"""Entry point: uv run python -m dealdata.load. Re-runnable. Owner: Member 1, Task 5.

Loads data/snapshot/products.json, the categories it uses, the stores and the demo
user into Postgres. Running it again updates rows, and never adds duplicates.
"""

import json
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import bcrypt
import yaml
from app.config import get_settings
from app.db import get_engine
from app.init_db import init_db
from app.models import Category, Store, StoreLocation, StoreProduct, User, UserStore
from app.textutil import fold
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealdata.tree import LeafRule, category_nodes, load_tree

DATA_DIR = Path(__file__).parents[1]
DEMO_EMAIL = "demo@dealdirection.ro"


def load_snapshot(
    db: Session, products: list[dict], stores: dict, rules: list[LeafRule]
) -> None:
    """Save the snapshot in db. The caller commits."""
    store_ids = _load_stores(db, stores)
    category_ids = _load_categories(db, products, rules)
    _load_products(db, products, store_ids, category_ids)
    _load_demo_user(db, store_ids)
    db.flush()


def _load_stores(db: Session, stores: dict) -> dict[str, int]:
    saved = {store.name: store for store in db.scalars(select(Store))}
    ids = {}
    for name, details in stores.items():
        store = saved.get(name) or Store(name=name)
        store.colour = details["colour"]
        db.add(store)
        db.flush()
        ids[name] = store.id
        _load_locations(db, store.id, details["locations"])
    return ids


def _load_locations(db: Session, store_id: int, locations: list[dict]) -> None:
    saved = {
        location.address: location
        for location in db.scalars(select(StoreLocation).where(StoreLocation.store_id == store_id))
    }
    for details in locations:
        location = saved.get(details["address"])
        if location is None:
            location = StoreLocation(store_id=store_id, address=details["address"])
            db.add(location)
        location.latitude = details["latitude"]
        location.longitude = details["longitude"]


def _load_categories(
    db: Session, products: list[dict], rules: list[LeafRule]
) -> dict[tuple[str, ...], int]:
    """Save the categories that products use, and return each row's id by its path."""
    used = {
        tuple(item["path"][: depth + 1])
        for item in products
        for depth in range(len(item["path"]))
    }
    saved = {(row.parent_id, row.name): row for row in db.scalars(select(Category))}
    ids: dict[tuple[str, ...], int] = {}
    for node in category_nodes(rules):
        if node.path not in used:
            continue
        parent_id = ids[node.parent] if node.parent else None
        row = saved.get((parent_id, node.path[-1]))
        if row is None:
            row = Category(parent_id=parent_id, name=node.path[-1])
            db.add(row)
        row.level = node.level
        row.size_amount = node.size_amount
        row.size_unit = node.size_unit
        row.aliases = list(node.aliases)
        db.flush()
        ids[node.path] = row.id
    return ids


def _load_products(
    db: Session,
    products: list[dict],
    store_ids: dict[str, int],
    category_ids: dict[tuple[str, ...], int],
) -> None:
    saved = {(row.store_id, row.name): row for row in db.scalars(select(StoreProduct))}
    for item in products:
        store_id = store_ids[item["store"]]
        path = tuple(item["path"])
        row = saved.get((store_id, item["name"]))
        if row is None:
            row = StoreProduct(store_id=store_id, name=item["name"])
            db.add(row)
        row.size_category_id = category_ids[path]
        row.type_category_id = category_ids[path[:-1]]
        row.brand = item["brand"]
        row.price = Decimal(item["price"])
        row.unit = item["unit"]
        row.source_url = item["source_url"]
        row.search_text = fold(" ".join(filter(None, (item["name"], item["brand"]))))
        row.updated_at = datetime.fromisoformat(item["updated_at"]).replace(tzinfo=UTC)


def _load_demo_user(db: Session, store_ids: dict[str, int]) -> None:
    """Keep an existing demo user's password, and select every store for it."""
    user = db.scalars(select(User).where(User.is_demo)).first()
    if user is None:
        # Demo login needs no password, so a blank setting becomes an unguessable one.
        password = get_settings().DEMO_PASSWORD or secrets.token_urlsafe(32)
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(email=DEMO_EMAIL, password_hash=hashed, is_demo=True)
        db.add(user)
        db.flush()

    selected = set(db.scalars(select(UserStore.store_id).where(UserStore.user_id == user.id)))
    for store_id in store_ids.values():
        if store_id not in selected:
            db.add(UserStore(user_id=user.id, store_id=store_id))


def main() -> None:
    products = json.loads((DATA_DIR / "snapshot" / "products.json").read_text(encoding="utf-8"))
    stores = yaml.safe_load((DATA_DIR / "stores.yaml").read_text(encoding="utf-8"))["stores"]
    rules = load_tree(DATA_DIR / "tree.yaml")

    init_db()
    with Session(get_engine()) as db:
        load_snapshot(db, products, stores, rules)
        db.commit()
    print(f"Loaded {len(products)} products from {len(stores)} stores")


if __name__ == "__main__":
    main()
