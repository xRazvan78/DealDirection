"""Task 11: POST /api/lists/{id}/receipts?store_id= with the real database.

The OCR reader is replaced by `fake_reader`, so no photos or OCR engine are
needed. Each test runs in a transaction that's rolled back afterwards.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import create_token
from app.documents.schemas import DocumentError, LineMatch, ReceiptData, ReceiptLine
from app.main import app
from app.models import (
    Category,
    ListItem,
    PointsLedger,
    Receipt,
    ReceiptLine as ReceiptLineRow,
    ShoppingList,
    Store,
    StoreProduct,
    User,
)
from app.receipts import router as receipts_router

PHOTO = ("bon.jpg", b"fake jpeg bytes", "image/jpeg")
DAY = datetime(2026, 10, 26, 11, 39)


# --- Fixtures ---------------------------------------------------------------


@dataclass
class ActiveList:
    id: int
    owner: User
    client: TestClient
    stores: list[Store]
    items: dict[str, ListItem]  # by product name


def _user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    return user


def _client(user: User) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {create_token(user)}"})


def _leaf(db: Session, name: str, amount: str, unit: str) -> tuple[Category, Category]:
    top = Category(name=f"{name} Test", level="category")
    db.add(top)
    db.flush()
    kind = Category(parent_id=top.id, name="Standard", level="type")
    db.add(kind)
    db.flush()
    size = Category(parent_id=kind.id, name=f"{amount} {unit}", level="size", size_amount=Decimal(amount), size_unit=unit)
    db.add(size)
    db.flush()
    return kind, size


def _make_list(db: Session, owner: User, parts: dict[Store, list[tuple[str, str, str]]]) -> ActiveList:
    """An activated list: each (product name, unit price, quantity) is assigned to its store."""
    shopping_list = ShoppingList(user_id=owner.id, name="Lista test", state="active")
    db.add(shopping_list)
    db.flush()
    items = {}
    for store, products in parts.items():
        for name, price, quantity in products:
            # A second list in the same store reuses the product, as in real data.
            product = db.scalars(
                select(StoreProduct).where(StoreProduct.store_id == store.id, StoreProduct.name == name)
            ).first()
            if product is None:
                kind, size = _leaf(db, name, "1", "kg" if "kg" in name.lower() else "buc")
                product = StoreProduct(
                    store_id=store.id,
                    size_category_id=size.id,
                    type_category_id=kind.id,
                    name=name,
                    brand=None,
                    price=Decimal(price),
                    unit=size.size_unit,
                    search_text=name.lower(),
                )
                db.add(product)
                db.flush()
            item = ListItem(
                list_id=shopping_list.id,
                size_category_id=product.size_category_id,
                quantity=Decimal(quantity),
                assigned_store_id=store.id,
                assigned_product_id=product.id,
                estimated_price=Decimal(price),
            )
            db.add(item)
            db.flush()
            items[name] = item
    return ActiveList(shopping_list.id, owner, _client(owner), list(parts), items)


@pytest.fixture
def stores(db: Session) -> list[Store]:
    made = [Store(name="Magazin Test A", colour="#d6001c"), Store(name="Magazin Test B", colour="#004e9f")]
    db.add_all(made)
    db.flush()
    return made


@pytest.fixture
def active_list(client: TestClient, db: Session, stores: list[Store]) -> ActiveList:
    """One store part: milk 10 lei and bread 5 lei (x2)."""
    owner = _user(db, "receipts-owner@example.com")
    return _make_list(
        db, owner, {stores[0]: [("Lapte integral Albalact 1 l", "10.00", "1"), ("Paine alba feliata", "5.00", "2")]}
    )


@pytest.fixture
def split_list(client: TestClient, db: Session, stores: list[Store]) -> ActiveList:
    """Two store parts: milk at store A, coffee at store B."""
    owner = _user(db, "receipts-split@example.com")
    return _make_list(
        db,
        owner,
        {stores[0]: [("Lapte integral Albalact 1 l", "10.00", "1")], stores[1]: [("Cafea macinata Tchibo", "30.00", "1")]},
    )


def receipt(store: str = "Magazin Test A", total: str = "20.00", lines=(), when: datetime | None = DAY) -> ReceiptData:
    return ReceiptData(
        store_name=store,
        purchased_at=when,
        total=Decimal(total) if total is not None else None,
        lines=[ReceiptLine(raw_text=t, quantity=Decimal(q), line_total=Decimal(p)) for t, q, p in lines],
    )


def upload(shopping: ActiveList, store: Store, file=PHOTO, client: TestClient | None = None):
    return (client or shopping.client).post(
        f"/api/lists/{shopping.id}/receipts", params={"store_id": store.id}, files={"file": file}
    )


def points_of(db: Session, user: User) -> int:
    return db.scalar(select(func.coalesce(func.sum(PointsLedger.amount), 0)).where(PointsLedger.user_id == user.id))


def receipts_of(db: Session, list_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Receipt).where(Receipt.list_id == list_id))


# --- Success ----------------------------------------------------------------


def test_matched_items_earn_points_and_a_ledger_entry(db: Session, active_list: ActiveList, fake_reader) -> None:
    milk, bread = active_list.items.values()
    fake_reader.receipt = receipt(total="20.00", lines=[("LAPTE ALB 1L", "1", "10.00"), ("PAINE ALBA", "2", "10.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id), LineMatch(line_index=1, item_id=bread.id)]

    response = upload(active_list, active_list.stores[0])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["estimate"] == "20.00"
    assert body["paid"] == "20.00"
    assert body["modifier"] == "1.00"
    assert body["points"] == 200
    assert [(m["name"], m["line_total"]) for m in body["matched"]] == [
        ("Lapte integral Albalact 1 l", "10.00"),
        ("Paine alba feliata", "10.00"),
    ]
    assert body["unmatched_items"] == []
    assert points_of(db, active_list.owner) == 200
    saved = db.scalars(select(Receipt).where(Receipt.list_id == active_list.id)).one()
    assert (saved.points, saved.estimate, saved.paid, saved.total) == (200, Decimal("20.00"), Decimal("20.00"), Decimal("20.00"))


def test_every_receipt_line_is_saved_with_its_match(db: Session, active_list: ActiveList, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(lines=[("LAPTE ALB 1L", "1", "10.00"), ("PUNGA", "1", "0.50")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]

    upload(active_list, active_list.stores[0])

    rows = db.scalars(select(ReceiptLineRow).order_by(ReceiptLineRow.id)).all()
    assert [(r.raw_text, r.matched_item_id) for r in rows[-2:]] == [("LAPTE ALB 1L", milk.id), ("PUNGA", None)]


def test_extra_lines_and_missing_items_earn_nothing(db: Session, active_list: ActiveList, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="60.50", lines=[("LAPTE ALB 1L", "1", "10.00"), ("WHISKY", "1", "50.50")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]

    body = upload(active_list, active_list.stores[0]).json()

    assert (body["estimate"], body["paid"], body["points"]) == ("10.00", "10.00", 100)
    assert body["unmatched_items"] == [{"item_id": active_list.items["Paine alba feliata"].id, "name": "Paine alba feliata"}]


def test_paying_twelve_percent_over_gives_x1_12(active_list: ActiveList, fake_reader) -> None:
    milk, bread = active_list.items.values()
    fake_reader.receipt = receipt(total="22.40", lines=[("LAPTE", "1", "11.20"), ("PAINE", "2", "11.20")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id), LineMatch(line_index=1, item_id=bread.id)]

    body = upload(active_list, active_list.stores[0]).json()

    assert (body["estimate"], body["paid"], body["modifier"], body["points"]) == ("20.00", "22.40", "1.12", 224)


def test_real_fuzzy_matching_through_the_route(active_list: ActiveList, fake_reader) -> None:
    # No fixed matches: the reader's real rapidfuzz matching pairs the lines.
    fake_reader.receipt = receipt(
        total="20.00", lines=[("PAINE ALBA FELIATA", "2", "10.00"), ("LAPTE INTEGRAL ALBALACT 1L", "1", "10.00")]
    )

    body = upload(active_list, active_list.stores[0]).json()

    assert sorted(m["name"] for m in body["matched"]) == ["Lapte integral Albalact 1 l", "Paine alba feliata"]
    assert body["points"] == 200


def test_split_list_needs_one_receipt_per_store(db: Session, split_list: ActiveList, fake_reader) -> None:
    milk, coffee = split_list.items.values()
    store_a, store_b = split_list.stores

    fake_reader.receipt = receipt("Magazin Test A", "10.00", [("LAPTE", "1", "10.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(split_list, store_a).status_code == 200
    assert db.get(ShoppingList, split_list.id).state == "active"

    fake_reader.receipt = receipt("Magazin Test B", "30.00", [("CAFEA", "1", "30.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=coffee.id)]
    assert upload(split_list, store_b).status_code == 200

    db.expire_all()
    assert db.get(ShoppingList, split_list.id).state == "completed"
    assert points_of(db, split_list.owner) == 400


def test_matching_only_uses_that_stores_part(split_list: ActiveList, fake_reader) -> None:
    coffee = split_list.items["Cafea macinata Tchibo"]
    fake_reader.receipt = receipt("Magazin Test A", "30.00", [("CAFEA", "1", "30.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=coffee.id)]  # coffee belongs to store B

    response = upload(split_list, split_list.stores[0])

    assert response.status_code == 422


# --- Using a receipt twice --------------------------------------------------


def test_same_receipt_on_another_account_is_rejected(db: Session, active_list: ActiveList, stores, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, stores[0]).status_code == 200

    other = _make_list(db, _user(db, "receipts-other@example.com"), {stores[0]: [("Lapte integral Albalact 1 l", "10.00", "1")]})
    fake_reader.matches = [LineMatch(line_index=0, item_id=other.items["Lapte integral Albalact 1 l"].id)]

    response = upload(other, stores[0])

    assert response.status_code == 409
    assert points_of(db, other.owner) == 0


def test_second_receipt_for_the_same_part_is_rejected(db: Session, active_list: ActiveList, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, active_list.stores[0]).status_code == 200

    fake_reader.receipt = receipt(total="11.00", lines=[("LAPTE", "1", "11.00")], when=datetime(2026, 10, 27))
    response = upload(active_list, active_list.stores[0])

    assert response.status_code == 409
    assert points_of(db, active_list.owner) == 100


def test_simultaneous_duplicate_adds_points_once(db: Session, active_list: ActiveList, fake_reader, monkeypatch) -> None:
    # Two uploads that both pass the early checks: the database's unique
    # fingerprint stops the second, and its transaction is rolled back.
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, active_list.stores[0]).status_code == 200

    monkeypatch.setattr(receipts_router, "_already_used", lambda *args: None)
    other = _make_list(db, _user(db, "receipts-race@example.com"), {active_list.stores[0]: [("Lapte integral Albalact 1 l", "10.00", "1")]})
    fake_reader.matches = [LineMatch(line_index=0, item_id=other.items["Lapte integral Albalact 1 l"].id)]

    response = upload(other, active_list.stores[0])

    assert response.status_code == 409
    assert points_of(db, other.owner) == 0
    assert receipts_of(db, other.id) == 0


# --- Rejected receipts ------------------------------------------------------


def test_wrong_store_is_rejected_naming_the_expected_store(db: Session, active_list: ActiveList, fake_reader) -> None:
    fake_reader.receipt = receipt(store="Lidl", lines=[("LAPTE", "1", "10.00")])

    response = upload(active_list, active_list.stores[0])

    assert response.status_code == 422
    assert "Magazin Test A" in response.json()["detail"]
    assert receipts_of(db, active_list.id) == 0


def test_unrecognised_store_is_rejected(active_list: ActiveList, fake_reader) -> None:
    fake_reader.receipt = receipt(store="", lines=[("LAPTE", "1", "10.00")])

    assert upload(active_list, active_list.stores[0]).status_code == 422


def test_unreadable_receipt_saves_nothing_and_can_be_retried(db: Session, active_list: ActiveList, fake_reader) -> None:
    fake_reader.error = DocumentError("unreadable")

    response = upload(active_list, active_list.stores[0])

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert receipts_of(db, active_list.id) == 0

    fake_reader.error = None
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, active_list.stores[0]).status_code == 200


@pytest.mark.parametrize(
    "bad",
    [
        receipt(when=None, lines=[("LAPTE", "1", "10.00")]),
        receipt(total=None, lines=[("LAPTE", "1", "10.00")]),
        receipt(lines=[]),
    ],
    ids=["no date", "no total", "no lines"],
)
def test_receipt_missing_date_total_or_lines_is_rejected(db: Session, active_list: ActiveList, fake_reader, bad) -> None:
    fake_reader.receipt = bad

    assert upload(active_list, active_list.stores[0]).status_code == 422
    assert receipts_of(db, active_list.id) == 0


def test_no_matches_is_rejected_and_the_receipt_stays_usable(db: Session, active_list: ActiveList, fake_reader) -> None:
    fake_reader.receipt = receipt(total="10.00", lines=[("WHISKY", "1", "10.00")])
    fake_reader.matches = []

    assert upload(active_list, active_list.stores[0]).status_code == 422
    assert points_of(db, active_list.owner) == 0

    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")])
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, active_list.stores[0]).status_code == 200


def test_draft_list_is_rejected(db: Session, active_list: ActiveList, fake_reader) -> None:
    db.get(ShoppingList, active_list.id).state = "draft"
    db.flush()
    fake_reader.receipt = receipt(lines=[("LAPTE", "1", "10.00")])

    assert upload(active_list, active_list.stores[0]).status_code == 409


def test_store_without_a_part_is_rejected(active_list: ActiveList, stores, fake_reader) -> None:
    # The list only buys from store A.
    fake_reader.receipt = receipt(store="Magazin Test B", lines=[("LAPTE", "1", "10.00")])

    assert upload(active_list, stores[1]).status_code == 422


def test_oversized_file_is_rejected(active_list: ActiveList, fake_reader, monkeypatch) -> None:
    monkeypatch.setattr(receipts_router, "_max_upload_bytes", lambda: 10)

    response = upload(active_list, active_list.stores[0], file=("bon.jpg", b"x" * 11, "image/jpeg"))

    assert response.status_code == 413
    assert fake_reader.calls == []


def test_wrong_file_type_is_rejected(active_list: ActiveList, fake_reader) -> None:
    response = upload(active_list, active_list.stores[0], file=("bon.pdf", b"%PDF", "application/pdf"))

    assert response.status_code == 415
    assert fake_reader.calls == []


# --- Ownership and login ----------------------------------------------------


def test_another_users_list_is_not_found(active_list: ActiveList, other_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = receipt(lines=[("LAPTE", "1", "10.00")])

    assert upload(active_list, active_list.stores[0], client=other_client).status_code == 404


def test_deleted_list_is_not_found(db: Session, active_list: ActiveList, fake_reader) -> None:
    db.get(ShoppingList, active_list.id).deleted_at = datetime(2026, 11, 1)
    db.flush()

    assert upload(active_list, active_list.stores[0]).status_code == 404


def test_unknown_store_is_not_found(active_list: ActiveList, fake_reader) -> None:
    response = active_list.client.post(
        f"/api/lists/{active_list.id}/receipts", params={"store_id": 999_999}, files={"file": PHOTO}
    )

    assert response.status_code == 404


def test_login_is_required(client: TestClient, active_list: ActiveList) -> None:
    response = client.post(f"/api/lists/{active_list.id}/receipts", params={"store_id": 1}, files={"file": PHOTO})

    assert response.status_code == 401


def test_completed_list_says_its_receipts_are_done(db: Session, active_list: ActiveList, fake_reader) -> None:
    db.get(ShoppingList, active_list.id).state = "completed"
    db.flush()
    fake_reader.receipt = receipt(lines=[("LAPTE", "1", "10.00")])

    response = upload(active_list, active_list.stores[0])

    assert response.status_code == 409
    assert "plan" not in response.json()["detail"]
