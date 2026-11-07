"""Task 11: POST /api/lists/{id}/receipts?store_id= with the real database.

The OCR reader is replaced by `fake_reader`, so no photos or OCR engine are
needed. Each test runs in a transaction that's rolled back afterwards.
"""

import json
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
from app.receipts.matching import receipt_code

PHOTO = ("bon.jpg", b"fake jpeg bytes", "image/jpeg")
DAY = datetime(2026, 10, 26, 11, 39)
BARCODE = "9264209507286283375840000001"  # made up: tests share a database with real receipts
OTHER_BARCODE = "9264238711852413082267699676"
ID_UNIC = "60010827022026102612373602640061"
OTHER_ID_UNIC = "60010827022026102612373602640062"
FISCAL_KEY = "6001082702|20261026|1237|61"


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


def scan_twice(db: Session, active_list: ActiveList, fake_reader, first: dict, second: dict, total: str = "10.00") -> int:
    """Upload a receipt for one list, then one for another. Returns the second status."""
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")]).model_copy(update=first)
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, active_list.stores[0]).status_code == 200

    other = _make_list(db, _user(db, "receipts-twice@example.com"), {active_list.stores[0]: [("Lapte integral Albalact 1 l", "10.00", "1")]})
    fake_reader.receipt = receipt(total=total, lines=[("LAPTE", "1", total)]).model_copy(update=second)
    fake_reader.matches = [LineMatch(line_index=0, item_id=other.items["Lapte integral Albalact 1 l"].id)]
    return upload(other, active_list.stores[0]).status_code


def test_same_barcode_is_rejected_even_if_the_total_was_misread(db: Session, active_list: ActiveList, fake_reader) -> None:
    status = scan_twice(db, active_list, fake_reader, {"barcode": BARCODE}, {"barcode": BARCODE}, total="19.00")

    assert status == 409


def test_same_id_unic_is_rejected_even_if_the_total_was_misread(db: Session, active_list: ActiveList, fake_reader) -> None:
    status = scan_twice(db, active_list, fake_reader, {"unique_id": ID_UNIC}, {"unique_id": ID_UNIC}, total="19.00")

    assert status == 409


def test_barcode_on_one_scan_and_id_unic_on_the_other_is_rejected(db: Session, active_list: ActiveList, fake_reader) -> None:
    assert scan_twice(db, active_list, fake_reader, {"barcode": BARCODE}, {"unique_id": ID_UNIC}) == 409


def test_fiscal_key_on_one_scan_and_none_on_the_other_is_rejected(db: Session, active_list: ActiveList, fake_reader) -> None:
    # The second scan missed the time, so it has no key, but it's the same paper.
    assert scan_twice(db, active_list, fake_reader, {"fiscal_key": FISCAL_KEY}, {}) == 409


def test_barcode_on_one_scan_and_fiscal_key_on_the_other_is_rejected(db: Session, active_list: ActiveList, fake_reader) -> None:
    assert scan_twice(db, active_list, fake_reader, {"barcode": BARCODE}, {"fiscal_key": FISCAL_KEY}) == 409


def test_the_fiscal_key_is_saved(db: Session, active_list: ActiveList, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")]).model_copy(update={"fiscal_key": FISCAL_KEY})
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]

    assert upload(active_list, active_list.stores[0]).status_code == 200
    assert db.scalars(select(Receipt).where(Receipt.list_id == active_list.id)).one().fiscal_key == FISCAL_KEY


def test_a_shared_code_counts_when_the_other_code_differs(db: Session, active_list: ActiveList, fake_reader) -> None:
    first = {"barcode": BARCODE, "unique_id": ID_UNIC}
    second = {"barcode": BARCODE, "unique_id": OTHER_ID_UNIC}

    assert scan_twice(db, active_list, fake_reader, first, second) == 409


def test_identical_shopping_with_different_barcodes_is_allowed(db: Session, active_list: ActiveList, fake_reader) -> None:
    assert scan_twice(db, active_list, fake_reader, {"barcode": BARCODE}, {"barcode": OTHER_BARCODE}) == 200


def test_identical_shopping_with_different_id_unic_is_allowed(db: Session, active_list: ActiveList, fake_reader) -> None:
    assert scan_twice(db, active_list, fake_reader, {"unique_id": ID_UNIC}, {"unique_id": OTHER_ID_UNIC}) == 200


def test_both_identifiers_are_saved(db: Session, active_list: ActiveList, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    codes = {"barcode": BARCODE, "unique_id": ID_UNIC}
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")]).model_copy(update=codes)
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]

    assert upload(active_list, active_list.stores[0]).status_code == 200
    saved = db.scalars(select(Receipt).where(Receipt.list_id == active_list.id)).one()
    assert (saved.barcode, saved.unique_id) == (BARCODE, ID_UNIC)


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
    # barcode stops the second, and its transaction is rolled back.
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")]).model_copy(update={"barcode": BARCODE})
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, active_list.stores[0]).status_code == 200

    monkeypatch.setattr(receipts_router, "_already_used", lambda *args: None)
    monkeypatch.setattr(receipts_router, "_used_before", lambda *args: False)
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


# --- POST /api/receipts/read ------------------------------------------------


def read(client: TestClient, file=PHOTO):
    return client.post("/api/receipts/read", files={"file": file})


def test_reading_returns_what_the_receipt_says(auth_client: TestClient, db: Session, fake_reader) -> None:
    fake_reader.receipt = ReceiptData(
        store_name="Lidl",
        purchased_at=datetime(2026, 10, 26, 11, 39),
        total=Decimal("25.97"),
        lines=[
            ReceiptLine(raw_text="Chips", quantity=Decimal("1.000"), line_total=Decimal("7.99")),
            ReceiptLine(raw_text="Suc", quantity=Decimal("1.000"), line_total=Decimal("9.99")),
            ReceiptLine(raw_text="Chips", quantity=Decimal("1.000"), line_total=Decimal("7.99")),
        ],
        identifier="Z 0347 / BF 0025",
    )
    receipts_before = db.scalar(select(func.count()).select_from(Receipt))

    response = read(auth_client)

    assert response.status_code == 200
    assert response.json() == {
        "store_name": "Lidl",
        "purchased_at": "2026-10-26T11:39:00",
        "identifier": "Z 0347 / BF 0025",
        "identifier_printed": True,
        "total": "25.97",
        "deposits": "0",
        "lines": [
            {"name": "Chips", "quantity": "2.000", "line_total": "15.98"},
            {"name": "Suc", "quantity": "1.000", "line_total": "9.99"},
        ],
    }
    assert db.scalar(select(func.count()).select_from(Receipt)) == receipts_before


def test_reading_generates_an_identifier_when_none_is_printed(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = ReceiptData(
        store_name="Magazin care nu e in baza de date",
        purchased_at=DAY,
        total=Decimal("7.99"),
        lines=[ReceiptLine(raw_text="Chips", quantity=Decimal(1), line_total=Decimal("7.99"))],
    )

    body = read(auth_client).json()

    assert body["identifier"] == receipt_code("Magazin care nu e in baza de date", DAY, Decimal("7.99"))
    assert body["identifier_printed"] is False


def test_generated_identifier_ignores_ocr_differences_in_a_rescan() -> None:
    first = receipt_code("Lidl", datetime(2026, 10, 26, 11, 39), Decimal("25.97"))

    assert first == receipt_code("LIDL", datetime(2026, 10, 26), Decimal("25.970"))
    assert first != receipt_code("Lidl", datetime(2026, 10, 26), Decimal("25.98"))


def test_reading_returns_bottle_deposits_apart_from_the_products(auth_client: TestClient, fake_reader) -> None:
    line = ReceiptLine(raw_text="Suc", quantity=Decimal(1), line_total=Decimal("7.99"))
    fake_reader.receipt = ReceiptData(
        store_name="Lidl", purchased_at=DAY, total=Decimal("8.49"), lines=[line], deposits=Decimal("0.50"),
    )

    body = read(auth_client).json()

    assert (body["deposits"], len(body["lines"])) == ("0.50", 1)


def test_reading_shows_the_barcode_first(auth_client: TestClient, fake_reader) -> None:
    line = ReceiptLine(raw_text="Chips", quantity=Decimal(1), line_total=Decimal("7.99"))
    fake_reader.receipt = ReceiptData(
        store_name="Lidl", purchased_at=DAY, total=Decimal("7.99"), lines=[line],
        identifier="BF 1", unique_id=ID_UNIC, barcode=BARCODE,
    )

    assert read(auth_client).json()["identifier"] == BARCODE


def test_reading_prefers_a_checked_id_unic_to_other_numbers(auth_client: TestClient, fake_reader) -> None:
    line = ReceiptLine(raw_text="Chips", quantity=Decimal(1), line_total=Decimal("7.99"))
    fake_reader.receipt = ReceiptData(
        store_name="Lidl", purchased_at=DAY, total=Decimal("7.99"), lines=[line], identifier="BF 1", unique_id=ID_UNIC,
    )

    body = read(auth_client).json()

    assert (body["identifier"], body["identifier_printed"]) == (ID_UNIC, True)


def test_reading_leaves_unread_fields_empty(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = ReceiptData(
        store_name="",
        purchased_at=None,
        total=None,
        lines=[ReceiptLine(raw_text="Chips", quantity=Decimal(1), line_total=Decimal("7.99"))],
    )

    body = read(auth_client).json()

    assert (body["store_name"], body["purchased_at"], body["identifier"], body["total"]) == (None, None, None, None)
    assert body["identifier_printed"] is False


def test_reading_without_products_asks_for_a_new_photo(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = ReceiptData(store_name="Lidl", purchased_at=DAY, total=Decimal("1.00"), lines=[])

    response = read(auth_client)

    assert response.status_code == 422
    assert response.json()["detail"] == receipts_router.UNREADABLE


def test_reading_failure_asks_for_a_new_photo(auth_client: TestClient, fake_reader) -> None:
    fake_reader.error = DocumentError("too blurry")

    assert read(auth_client).status_code == 422


def test_reading_rejects_files_that_are_not_photos(auth_client: TestClient, fake_reader) -> None:
    assert read(auth_client, ("bon.pdf", b"%PDF", "application/pdf")).status_code == 415
    assert fake_reader.calls == []


def test_reading_needs_a_login(client: TestClient, fake_reader) -> None:
    assert read(client).status_code == 401


# --- Fiscal key and the total check -----------------------------------------


def test_two_receipts_with_the_same_total_and_day_but_different_fiscal_ids_both_count(db: Session, active_list: ActiveList, stores, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")]).model_copy(update={"fiscal_key": "111|20261026|1139|240"})
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, stores[0]).status_code == 200

    other = _make_list(db, _user(db, "receipts-fiscal@example.com"), {stores[0]: [("Lapte integral Albalact 1 l", "10.00", "1")]})
    fake_reader.receipt = fake_reader.receipt.model_copy(update={"fiscal_key": "111|20261026|1141|241"})
    fake_reader.matches = [LineMatch(line_index=0, item_id=other.items["Lapte integral Albalact 1 l"].id)]

    assert upload(other, stores[0]).status_code == 200


def test_same_fiscal_id_with_a_misread_total_is_still_a_duplicate(db: Session, active_list: ActiveList, stores, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")]).model_copy(update={"fiscal_key": "111|20261026|1139|240"})
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]
    assert upload(active_list, stores[0]).status_code == 200

    other = _make_list(db, _user(db, "receipts-misread@example.com"), {stores[0]: [("Lapte integral Albalact 1 l", "10.00", "1")]})
    fake_reader.receipt = receipt(total="16.00", lines=[("LAPTE", "1", "10.00")]).model_copy(update={"fiscal_key": "111|20261026|1139|240"})
    fake_reader.matches = [LineMatch(line_index=0, item_id=other.items["Lapte integral Albalact 1 l"].id)]

    assert upload(other, stores[0]).status_code == 409


def test_result_says_whether_the_receipt_adds_up(active_list: ActiveList, fake_reader) -> None:
    milk = active_list.items["Lapte integral Albalact 1 l"]
    fake_reader.receipt = receipt(total="10.00", lines=[("LAPTE", "1", "10.00")]).model_copy(update={"adds_up": True})
    fake_reader.matches = [LineMatch(line_index=0, item_id=milk.id)]

    assert upload(active_list, active_list.stores[0]).json()["adds_up"] is True


# --- POST /api/receipts/accept ----------------------------------------------


CART = [{"name": "Lapte Zuzu", "quantity": "1", "price": "10.00"}]
SHOP = receipt(store="Kaufland", total="12.00", lines=[("LAPTE ZUZU", "1", "12.00")])


def accept(client: TestClient, items=CART, file=PHOTO):
    return client.post(
        "/api/receipts/accept", data={"name": "Lista 1", "items": json.dumps(items)}, files={"file": file}
    )


def test_accepting_gives_points_for_the_matched_products(auth_client: TestClient, db: Session, fake_reader) -> None:
    fake_reader.receipt = SHOP

    response = accept(auth_client)

    assert response.status_code == 200
    assert response.json() == {"points": 120}  # 10 lei, paid 20% over: x1.20
    saved = db.scalars(select(Receipt).where(Receipt.total == Decimal("12.00"))).one()
    assert db.get(ShoppingList, saved.list_id).state == "completed"
    assert db.scalars(select(PointsLedger).where(PointsLedger.amount == 120)).one().reason == "Bon Kaufland"


def test_accepting_twice_is_rejected_and_gives_points_once(auth_client: TestClient, db: Session, fake_reader) -> None:
    fake_reader.receipt = SHOP
    accept(auth_client)

    response = accept(auth_client)

    assert response.status_code == 409
    assert db.scalar(select(func.count()).select_from(PointsLedger).where(PointsLedger.amount == 120)) == 1


def test_a_high_price_on_the_device_earns_no_more_than_was_paid(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = SHOP

    response = accept(auth_client, [{"name": "Lapte Zuzu", "quantity": "1", "price": "9000.00"}])

    assert response.json() == {"points": 120}


def test_each_unlisted_product_earns_five_points(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = receipt(
        store="Kaufland",
        total="17.00",
        lines=[("LAPTE ZUZU", "1", "10.00"), ("BOMBOANE", "2", "4.00"), ("SUC MERE", "1", "3.00")],
    )

    assert accept(auth_client).json() == {"points": 110}  # 100 for the milk, 5 for each of the others


def test_a_receipt_with_nothing_on_the_list_earns_five_per_product(auth_client: TestClient, db: Session, fake_reader) -> None:
    fake_reader.receipt = SHOP

    response = accept(auth_client, [{"name": "Bicicleta", "quantity": "1", "price": "10.00"}])

    assert response.json() == {"points": 5}
    assert db.scalars(select(PointsLedger).where(PointsLedger.amount == 5)).one()


def test_a_listed_product_without_a_price_counts_as_unlisted(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = SHOP

    assert accept(auth_client, [{"name": "Lapte Zuzu", "quantity": "1", "price": "0"}]).json() == {"points": 5}


def test_accepting_needs_a_store_date_and_total(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = receipt(store="", lines=[("LAPTE ZUZU", "1", "12.00")])

    assert accept(auth_client).status_code == 422


def test_accepting_rejects_malformed_items(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = SHOP

    assert accept(auth_client, [{"name": "Lapte", "quantity": "-1", "price": "1"}]).status_code == 422


def test_a_store_added_by_a_receipt_is_not_offered_for_comparing(auth_client: TestClient, fake_reader) -> None:
    fake_reader.receipt = SHOP
    accept(auth_client)

    assert "Kaufland" not in [store["name"] for store in auth_client.get("/api/stores").json()]


def test_accepting_needs_a_login(client: TestClient, fake_reader) -> None:
    assert accept(client).status_code == 401


# --- The demo user ----------------------------------------------------------


CODED_SHOP = ReceiptData(
    store_name="Kaufland",
    purchased_at=DAY,
    total=Decimal("12.00"),
    barcode=BARCODE,
    unique_id=ID_UNIC,
    fiscal_key=FISCAL_KEY,
    lines=SHOP.lines,
)


def _demo_client(db: Session) -> TestClient:
    user = _user(db, "demo-receipts@example.com")
    user.is_demo = True
    db.flush()
    return _client(user)


def test_the_demo_user_can_use_a_receipt_again_and_earn_again(client: TestClient, db: Session, fake_reader) -> None:
    fake_reader.receipt = CODED_SHOP
    demo = _demo_client(db)

    assert accept(demo).status_code == 200
    assert accept(demo).status_code == 200

    assert demo.get("/api/wallet").json()["balance"] == 240


def test_a_receipt_the_demo_user_used_stays_free_for_real_clients(auth_client: TestClient, db: Session, fake_reader) -> None:
    fake_reader.receipt = CODED_SHOP
    accept(_demo_client(db))

    assert accept(auth_client).status_code == 200


def test_the_demo_user_can_use_a_receipt_a_real_client_used(auth_client: TestClient, db: Session, fake_reader) -> None:
    fake_reader.receipt = CODED_SHOP
    accept(auth_client)

    assert accept(_demo_client(db)).status_code == 200


def test_a_real_client_cannot_use_a_receipt_twice_on_any_account(auth_client: TestClient, db: Session, fake_reader) -> None:
    fake_reader.receipt = CODED_SHOP
    accept(auth_client)
    other = _client(_user(db, "other-receipts@example.com"))

    assert accept(auth_client).status_code == 409
    assert accept(other).status_code == 409
