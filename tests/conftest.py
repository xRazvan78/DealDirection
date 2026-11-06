"""Shared fixtures, including the auth clients from Task 6.

Tests use the one `dealdirection` database. Each test runs inside a transaction
that is rolled back, so it leaves no data behind and never drops anything.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, get_engine
from app.deps import create_token
from app.init_db import init_db
from app.main import app
from app.models import Category, Store, StoreProduct, User


@dataclass(frozen=True)
class Sample:
    stores: tuple[Store, Store]
    category: Category
    type: Category
    size: Category
    products: tuple[StoreProduct, StoreProduct, StoreProduct]


@pytest.fixture(scope="session")
def _tables() -> None:
    init_db()


@pytest.fixture
def db(_tables: None) -> Iterator[Session]:
    """A session whose commits stay inside a transaction rolled back after the test."""
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _user(db: Session, email: str, is_demo: bool = False) -> User:
    user = User(email=email, password_hash="not-a-real-hash", is_demo=is_demo)
    db.add(user)
    db.flush()
    return user


def _client_for(user: User) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {create_token(user)}"})


@pytest.fixture
def auth_client(client: TestClient, db: Session) -> TestClient:
    """A client logged in as one user."""
    return _client_for(_user(db, "auth-client@example.com"))


@pytest.fixture
def other_client(client: TestClient, db: Session) -> TestClient:
    """A client logged in as a different user, for ownership tests."""
    return _client_for(_user(db, "other-client@example.com"))


@pytest.fixture
def demo_user(db: Session) -> User:
    """The demo user, created when the database has none loaded."""
    return db.scalars(select(User).where(User.is_demo)).first() or _user(
        db, "demo-test@example.com", is_demo=True
    )


@pytest.fixture
def sample(db: Session) -> Sample:
    """2 stores, Lapte → 3.5% → 1 l, and 3 products."""
    store_a = Store(name="Magazin Test A", colour="#d6001c")
    store_b = Store(name="Magazin Test B", colour="#004e9f")
    category = Category(name="Lapte Test", level="category")
    db.add_all([store_a, store_b, category])
    db.flush()

    type_ = Category(parent_id=category.id, name="3.5%", level="type")
    db.add(type_)
    db.flush()

    size = Category(
        parent_id=type_.id,
        name="1 l",
        level="size",
        size_amount=Decimal("1"),
        size_unit="l",
    )
    db.add(size)
    db.flush()

    def product(store: Store, name: str, brand: str, price: str) -> StoreProduct:
        return StoreProduct(
            store_id=store.id,
            size_category_id=size.id,
            type_category_id=type_.id,
            name=name,
            brand=brand,
            price=Decimal(price),
            unit="l",
            search_text=f"{name} {brand}".lower(),
        )

    products = (
        product(store_a, "Lapte Albalact 3.5% 1 l", "Albalact", "8.50"),
        product(store_a, "Lapte Zuzu 3.5% 1 l", "Zuzu", "9.20"),
        product(store_b, "Lapte Albalact 3.5% 1l", "Albalact", "7.90"),
    )
    db.add_all(products)
    db.flush()
    return Sample((store_a, store_b), category, type_, size, products)
