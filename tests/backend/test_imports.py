"""Task 12: POST /api/imports and POST /api/imports/confirm, with the real database.

The reader is `fake_reader`, so no OCR is needed; its food mapping is the real
fuzzy matching. Test categories use made-up words (testorez, testlapte) so the
real catalogue in the database can't interfere.
"""

from dataclasses import dataclass
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.schemas import DocumentError, Food, FoodList
from app.imports import router as imports_router
from app.models import Category, ListItem, ShoppingList, Store, StoreProduct, User


@dataclass
class Catalog:
    rice_500g: int
    rice_1kg: int
    milk_1l: int  # the common milk type (more products)
    other_milk_1l: int
    milk_type: int  # a type-level id, never valid as a list item


def _add(db: Session, **fields) -> Category:
    category = Category(**fields)
    db.add(category)
    db.flush()
    return category


def _products(db: Session, store: Store, kind: Category, size: Category, count: int) -> None:
    for n in range(count):
        name = f"{kind.name} {size.name} {n}"
        db.add(
            StoreProduct(
                store_id=store.id, size_category_id=size.id, type_category_id=kind.id, name=name,
                price=Decimal("5"), unit=size.size_unit, search_text=name.lower(),
            )
        )
    db.flush()


@pytest.fixture
def catalog(db: Session) -> Catalog:
    store = Store(name="Magazin Import Test", colour="#123456")
    db.add(store)
    db.flush()
    group = _add(db, name="Grup Test", level="category")

    rice = _add(db, parent_id=group.id, name="Testorez", level="category")
    basmati = _add(db, parent_id=rice.id, name="Basmati", level="type")
    rice_500g = _add(db, parent_id=basmati.id, name="500 g", level="size", size_amount=Decimal("0.5"), size_unit="kg", aliases=["testorez"])
    rice_1kg = _add(db, parent_id=basmati.id, name="1 kg", level="size", size_amount=Decimal("1"), size_unit="kg", aliases=["testorez"])
    _products(db, store, basmati, rice_500g, 1)
    _products(db, store, basmati, rice_1kg, 1)

    milk = _add(db, parent_id=group.id, name="Testlapte", level="category")
    common = _add(db, parent_id=milk.id, name="3.5%", level="type")
    other = _add(db, parent_id=milk.id, name="Alte tipuri", level="type")
    # The rarer type gets the lower id, so a lowest-id tie rule would pick it.
    other_1l = _add(db, parent_id=other.id, name="1 l", level="size", size_amount=Decimal("1"), size_unit="l", aliases=["testlapte"])
    common_1l = _add(db, parent_id=common.id, name="1 l", level="size", size_amount=Decimal("1"), size_unit="l", aliases=["testlapte"])
    _products(db, store, other, other_1l, 1)
    _products(db, store, common, common_1l, 3)
    return Catalog(rice_500g.id, rice_1kg.id, common_1l.id, other_1l.id, common.id)


@pytest.fixture
def importer(client: TestClient, db: Session) -> tuple[TestClient, User]:
    from app.deps import create_token
    from app.main import app

    user = User(email="importer@example.com", password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    return TestClient(app, headers={"Authorization": f"Bearer {create_token(user)}"}), user


def foods(*items: tuple[str, str, str, bool], plan_days: int | None = None) -> FoodList:
    return FoodList(
        plan_days=plan_days,
        foods=[Food(name=n, amount=Decimal(a), unit=u, per_day=d) for n, a, u, d in items],
    )


def preview(client: TestClient, days: int | str = 7, text: str | None = "x", file=None):
    data = {"days": str(days)}
    if text is not None:
        data["text"] = text
    return client.post("/api/imports", data=data, files={"file": file} if file else None)


# --- Preview ----------------------------------------------------------------


def test_preview_scales_rounds_up_and_maps(importer, catalog: Catalog, fake_reader) -> None:
    client, _ = importer
    fake_reader.foods = foods(("testorez", "200", "g", True))

    response = preview(client, days=7)

    assert response.status_code == 200, response.text
    # 200 g a day for 7 days is 1.4 kg: 3 x 500 g beats 2 x 1 kg.
    assert response.json() == {
        "items": [{"food": "testorez", "size_category_id": catalog.rice_500g, "path": "Grup Test > Testorez > Basmati > 500 g", "packs": 3}],
        "unmapped": [],
    }


def test_plan_over_more_days_doubles(importer, catalog: Catalog, fake_reader) -> None:
    client, _ = importer
    fake_reader.foods = foods(("testorez", "500", "g", False), plan_days=7)

    item = preview(client, days=14).json()["items"][0]

    assert (item["size_category_id"], item["packs"]) == (catalog.rice_1kg, 1)


def test_repeated_foods_are_added_up(importer, catalog: Catalog, fake_reader) -> None:
    client, _ = importer
    fake_reader.foods = foods(("testorez", "500", "g", False), ("Testorez", "500", "g", False))

    items = preview(client, days=1).json()["items"]

    assert [(i["size_category_id"], i["packs"]) for i in items] == [(catalog.rice_1kg, 1)]


def test_common_type_wins_a_shared_alias(importer, catalog: Catalog, fake_reader) -> None:
    client, _ = importer
    fake_reader.foods = foods(("testlapte", "1", "l", False))

    assert preview(client, days=1).json()["items"][0]["size_category_id"] == catalog.milk_1l


def test_unknown_food_is_flagged(importer, catalog: Catalog, fake_reader) -> None:
    client, _ = importer
    fake_reader.foods = foods(("testorez", "1", "kg", False), ("zzqxw ghimbir", "50", "g", True))

    body = preview(client, days=1).json()

    assert [i["food"] for i in body["items"]] == ["testorez"]
    assert body["unmapped"] == ["zzqxw ghimbir"]


def test_food_in_an_incompatible_unit_is_flagged(importer, catalog: Catalog, fake_reader) -> None:
    client, _ = importer
    fake_reader.foods = foods(("testorez", "2", "l", False))  # rice is sold by weight

    assert preview(client, days=1).json() == {"items": [], "unmapped": ["testorez"]}


@pytest.mark.parametrize(
    ("name", "content", "media_type"),
    [("plan.pdf", b"%PDF-1.4", "application/pdf"), ("lista.jpg", b"jpeg", "image/jpeg"), ("lista.png", b"png", "image/png")],
)
def test_pdf_and_images_return_a_preview(importer, catalog: Catalog, fake_reader, name, content, media_type) -> None:
    client, _ = importer
    fake_reader.foods = foods(("testorez", "1", "kg", False))

    response = preview(client, days=1, text=None, file=(name, content, media_type))

    assert response.status_code == 200, response.text
    assert fake_reader.calls[0] == "read_foods"


def test_text_returns_a_preview(importer, catalog: Catalog, fake_reader) -> None:
    client, _ = importer
    fake_reader.foods = foods(("testorez", "1", "kg", False))

    assert preview(client, days=1, text="1 kg testorez").status_code == 200


def test_both_inputs_are_rejected(importer, fake_reader) -> None:
    client, _ = importer

    response = preview(client, text="1 kg orez", file=("lista.jpg", b"jpeg", "image/jpeg"))

    assert response.status_code == 422
    assert fake_reader.calls == []


@pytest.mark.parametrize("text", [None, "   "])
def test_no_input_is_rejected(importer, fake_reader, text) -> None:
    client, _ = importer

    assert preview(client, text=text).status_code == 422


@pytest.mark.parametrize("days", [0, -3, "abc"])
def test_days_must_be_positive(importer, fake_reader, days) -> None:
    client, _ = importer

    assert preview(client, days=days).status_code == 422


def test_nothing_usable_is_rejected(importer, fake_reader) -> None:
    client, _ = importer
    fake_reader.foods = foods()

    response = preview(client)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_reader_failure_is_rejected(importer, fake_reader) -> None:
    client, _ = importer
    fake_reader.error = DocumentError("unreadable")

    assert preview(client).status_code == 422


def test_wrong_file_type_is_rejected(importer, fake_reader) -> None:
    client, _ = importer

    assert preview(client, text=None, file=("lista.zip", b"zip", "application/zip")).status_code == 415


def test_oversized_file_is_rejected(importer, fake_reader, monkeypatch) -> None:
    client, _ = importer
    monkeypatch.setattr(imports_router, "_max_upload_bytes", lambda: 10)

    assert preview(client, text=None, file=("plan.pdf", b"x" * 11, "application/pdf")).status_code == 413


def test_preview_needs_login(client: TestClient, fake_reader) -> None:
    assert preview(client).status_code == 401


# --- Confirm ----------------------------------------------------------------


def confirm(client: TestClient, name: str = "Plan 7 zile", items=()):
    return client.post("/api/imports/confirm", json={"name": name, "items": list(items)})


def test_confirm_creates_a_draft_list(db: Session, importer, catalog: Catalog) -> None:
    client, user = importer

    response = confirm(client, items=[{"size_category_id": catalog.rice_500g, "packs": 3}, {"size_category_id": catalog.milk_1l, "packs": 2}])

    assert response.status_code == 201, response.text
    created = db.get(ShoppingList, response.json()["list_id"])
    assert (created.user_id, created.name, created.state) == (user.id, "Plan 7 zile", "draft")
    items = db.scalars(select(ListItem).where(ListItem.list_id == created.id).order_by(ListItem.id)).all()
    assert [(i.size_category_id, i.quantity, i.chosen_product_id) for i in items] == [
        (catalog.rice_500g, Decimal("3"), None),
        (catalog.milk_1l, Decimal("2"), None),
    ]


def test_confirm_adds_up_repeated_sizes(db: Session, importer, catalog: Catalog) -> None:
    client, _ = importer

    list_id = confirm(client, items=[{"size_category_id": catalog.rice_1kg, "packs": 1}, {"size_category_id": catalog.rice_1kg, "packs": 2}]).json()["list_id"]

    assert [i.quantity for i in db.scalars(select(ListItem).where(ListItem.list_id == list_id))] == [Decimal("3")]


@pytest.mark.parametrize(
    "body",
    [
        {"name": "Lista", "items": []},
        {"name": "  ", "items": [{"size_category_id": 1, "packs": 1}]},
        {"name": "Lista", "items": [{"size_category_id": 1, "packs": 0}]},
    ],
    ids=["no items", "blank name", "zero packs"],
)
def test_confirm_rejects_bad_input(importer, body) -> None:
    client, _ = importer

    assert client.post("/api/imports/confirm", json=body).status_code == 422


def test_confirm_rejects_unknown_or_non_size_categories(importer, catalog: Catalog) -> None:
    client, _ = importer

    assert confirm(client, items=[{"size_category_id": 999_999_999, "packs": 1}]).status_code == 422
    assert confirm(client, items=[{"size_category_id": catalog.milk_type, "packs": 1}]).status_code == 422


def test_confirm_needs_login(client: TestClient, catalog: Catalog) -> None:
    assert confirm(client, items=[{"size_category_id": catalog.rice_1kg, "packs": 1}]).status_code == 401
