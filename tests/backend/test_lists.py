from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Category, ListItem, ShoppingList


def new_list(client: TestClient, name: str = "Cumpărături") -> dict:
    response = client.post("/api/lists", json={"name": name})
    assert response.status_code == 201
    return response.json()


def add_item(client: TestClient, list_id: int, **fields: Any) -> dict:
    response = client.post(f"/api/lists/{list_id}/items", json=fields)
    assert response.status_code == 201
    return response.json()


def set_state(db: Session, list_id: int, state: str) -> None:
    db.get(ShoppingList, list_id).state = state
    db.commit()


def deleted_ago(db: Session, list_id: int, days: int) -> None:
    db.get(ShoppingList, list_id).deleted_at = datetime.now(UTC) - timedelta(days=days)
    db.commit()


# Lists


def test_routes_need_a_login(client: TestClient) -> None:
    assert client.get("/api/lists").status_code == 401


def test_create_starts_an_empty_draft(auth_client: TestClient) -> None:
    created = new_list(auth_client, "Sâmbătă")

    assert created["name"] == "Sâmbătă"
    assert created["state"] == "draft"
    assert created["items"] == []


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_create_rejects_a_bad_name(auth_client: TestClient, name: str) -> None:
    assert auth_client.post("/api/lists", json={"name": name}).status_code == 422


def test_read_returns_the_list_with_its_items(auth_client: TestClient, sample: Any) -> None:
    created = new_list(auth_client)
    item = add_item(auth_client, created["id"], size_category_id=sample.size.id, quantity="2")

    read = auth_client.get(f"/api/lists/{created['id']}")

    assert read.status_code == 200
    assert read.json()["items"] == [item]


def test_listing_shows_newest_first_with_items(auth_client: TestClient, sample: Any) -> None:
    older = new_list(auth_client, "Veche")
    newer = new_list(auth_client, "Nouă")
    add_item(auth_client, older["id"], size_category_id=sample.size.id, quantity="1")

    lists = auth_client.get("/api/lists").json()

    assert [row["id"] for row in lists] == [newer["id"], older["id"]]
    assert [len(row["items"]) for row in lists] == [0, 1]


def test_rename_changes_the_name(auth_client: TestClient) -> None:
    created = new_list(auth_client)

    renamed = auth_client.patch(f"/api/lists/{created['id']}", json={"name": "Altă listă"})

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Altă listă"
    assert auth_client.get(f"/api/lists/{created['id']}").json()["name"] == "Altă listă"


def test_delete_keeps_the_row_and_hides_the_list(auth_client: TestClient, db: Session) -> None:
    created = new_list(auth_client)

    response = auth_client.delete(f"/api/lists/{created['id']}")

    assert response.status_code == 204
    assert db.get(ShoppingList, created["id"]).deleted_at is not None
    assert auth_client.get(f"/api/lists/{created['id']}").status_code == 404
    assert auth_client.get("/api/lists").json() == []


def test_normal_routes_skip_a_deleted_list(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]
    auth_client.delete(f"/api/lists/{list_id}")

    assert auth_client.patch(f"/api/lists/{list_id}", json={"name": "x"}).status_code == 404
    assert auth_client.delete(f"/api/lists/{list_id}").status_code == 404
    assert auth_client.post(f"/api/lists/{list_id}/complete").status_code == 404
    item = {"size_category_id": sample.size.id, "quantity": "1"}
    assert auth_client.post(f"/api/lists/{list_id}/items", json=item).status_code == 404


def test_another_users_list_gives_404(
    auth_client: TestClient, other_client: TestClient, sample: Any
) -> None:
    list_id = new_list(auth_client)["id"]
    item = add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="1")
    item_url = f"/api/lists/{list_id}/items/{item['id']}"

    assert other_client.get("/api/lists").json() == []
    assert other_client.get(f"/api/lists/{list_id}").status_code == 404
    assert other_client.patch(f"/api/lists/{list_id}", json={"name": "x"}).status_code == 404
    assert other_client.delete(f"/api/lists/{list_id}").status_code == 404
    assert other_client.post(f"/api/lists/{list_id}/complete").status_code == 404
    new_item = {"size_category_id": sample.size.id, "quantity": "1"}
    assert other_client.post(f"/api/lists/{list_id}/items", json=new_item).status_code == 404
    assert other_client.patch(item_url, json={"quantity": "2"}).status_code == 404
    assert other_client.delete(item_url).status_code == 404


def test_complete_sets_the_state(auth_client: TestClient, db: Session) -> None:
    list_id = new_list(auth_client)["id"]
    set_state(db, list_id, "active")

    completed = auth_client.post(f"/api/lists/{list_id}/complete")

    assert completed.status_code == 200
    assert completed.json()["state"] == "completed"


# Items


def test_add_a_generic_item(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]

    item = add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="1.5")

    assert item["size_category_id"] == sample.size.id
    assert item["chosen_product_id"] is None
    assert item["brand"] is None
    assert Decimal(item["quantity"]) == Decimal("1.5")
    assert item["removed"] is False


def test_add_a_brand_item_copies_the_brand(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]
    product = sample.products[1]

    item = add_item(
        auth_client,
        list_id,
        size_category_id=sample.size.id,
        quantity="1",
        chosen_product_id=product.id,
    )

    assert item["chosen_product_id"] == product.id
    assert item["brand"] == "Zuzu"


def test_adding_the_same_generic_item_adds_the_quantity(
    auth_client: TestClient, sample: Any
) -> None:
    list_id = new_list(auth_client)["id"]

    add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="1")
    item = add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="2.5")

    assert Decimal(item["quantity"]) == Decimal("3.5")
    assert len(auth_client.get(f"/api/lists/{list_id}").json()["items"]) == 1


def test_adding_the_same_brand_item_adds_the_quantity(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]
    fields = {
        "size_category_id": sample.size.id,
        "chosen_product_id": sample.products[0].id,
        "quantity": "1",
    }

    add_item(auth_client, list_id, **fields)
    item = add_item(auth_client, list_id, **fields)

    assert Decimal(item["quantity"]) == Decimal("2")


def test_generic_and_brand_items_stay_separate(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]
    size_id = sample.size.id

    add_item(auth_client, list_id, size_category_id=size_id, quantity="1")
    add_item(
        auth_client,
        list_id,
        size_category_id=size_id,
        quantity="1",
        chosen_product_id=sample.products[0].id,
    )
    add_item(
        auth_client,
        list_id,
        size_category_id=size_id,
        quantity="1",
        chosen_product_id=sample.products[1].id,
    )

    assert len(auth_client.get(f"/api/lists/{list_id}").json()["items"]) == 3


def test_the_same_item_on_two_lists_stays_separate(auth_client: TestClient, sample: Any) -> None:
    first = new_list(auth_client, "Prima")["id"]
    second = new_list(auth_client, "A doua")["id"]

    add_item(auth_client, first, size_category_id=sample.size.id, quantity="1")
    item = add_item(auth_client, second, size_category_id=sample.size.id, quantity="1")

    assert Decimal(item["quantity"]) == Decimal("1")


@pytest.mark.parametrize("quantity", ["0", "-1", "0.0001", "abc", "10000"])
def test_add_rejects_a_bad_quantity(auth_client: TestClient, sample: Any, quantity: str) -> None:
    list_id = new_list(auth_client)["id"]

    response = auth_client.post(
        f"/api/lists/{list_id}/items",
        json={"size_category_id": sample.size.id, "quantity": quantity},
    )

    assert response.status_code == 422


def test_merging_past_the_maximum_gives_422(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]
    item = {"size_category_id": sample.size.id, "quantity": "9999"}
    add_item(auth_client, list_id, **item)

    response = auth_client.post(f"/api/lists/{list_id}/items", json=item)

    assert response.status_code == 422


def test_add_rejects_an_unknown_category(auth_client: TestClient) -> None:
    list_id = new_list(auth_client)["id"]

    response = auth_client.post(
        f"/api/lists/{list_id}/items", json={"size_category_id": 0, "quantity": "1"}
    )

    assert response.status_code == 422


def test_add_rejects_a_category_that_is_not_a_size(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]

    response = auth_client.post(
        f"/api/lists/{list_id}/items",
        json={"size_category_id": sample.type.id, "quantity": "1"},
    )

    assert response.status_code == 422


def test_add_rejects_an_unknown_product(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]

    response = auth_client.post(
        f"/api/lists/{list_id}/items",
        json={"size_category_id": sample.size.id, "quantity": "1", "chosen_product_id": 0},
    )

    assert response.status_code == 422


def test_add_rejects_a_product_from_another_size(
    auth_client: TestClient, sample: Any, db: Session
) -> None:
    list_id = new_list(auth_client)["id"]
    other_size = Category(parent_id=sample.type.id, name="2 l", level="size")
    db.add(other_size)
    db.flush()

    response = auth_client.post(
        f"/api/lists/{list_id}/items",
        json={
            "size_category_id": other_size.id,
            "quantity": "1",
            "chosen_product_id": sample.products[0].id,
        },
    )

    assert response.status_code == 422


def test_update_sets_the_quantity(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]
    item = add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="1")

    updated = auth_client.patch(f"/api/lists/{list_id}/items/{item['id']}", json={"quantity": "4"})

    assert updated.status_code == 200
    assert Decimal(updated.json()["quantity"]) == Decimal("4")


def test_update_rejects_zero_quantity(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]
    item = add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="1")

    response = auth_client.patch(f"/api/lists/{list_id}/items/{item['id']}", json={"quantity": "0"})

    assert response.status_code == 422


def test_delete_removes_the_item(auth_client: TestClient, sample: Any, db: Session) -> None:
    list_id = new_list(auth_client)["id"]
    item = add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="1")

    response = auth_client.delete(f"/api/lists/{list_id}/items/{item['id']}")

    assert response.status_code == 204
    assert db.get(ListItem, item["id"]) is None
    assert auth_client.get(f"/api/lists/{list_id}").json()["items"] == []


def test_an_item_on_another_list_gives_404(auth_client: TestClient, sample: Any) -> None:
    first = new_list(auth_client, "Prima")["id"]
    second = new_list(auth_client, "A doua")["id"]
    item = add_item(auth_client, first, size_category_id=sample.size.id, quantity="1")
    url = f"/api/lists/{second}/items/{item['id']}"

    assert auth_client.patch(url, json={"quantity": "2"}).status_code == 404
    assert auth_client.delete(url).status_code == 404


@pytest.mark.parametrize("state", ["active", "completed"])
def test_items_are_locked_once_the_list_leaves_draft(
    auth_client: TestClient, sample: Any, db: Session, state: str
) -> None:
    list_id = new_list(auth_client)["id"]
    item = add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="1")
    url = f"/api/lists/{list_id}/items"
    set_state(db, list_id, state)

    added = auth_client.post(url, json={"size_category_id": sample.size.id, "quantity": "1"})
    updated = auth_client.patch(f"{url}/{item['id']}", json={"quantity": "2"})
    deleted = auth_client.delete(f"{url}/{item['id']}")

    assert (added.status_code, updated.status_code, deleted.status_code) == (409, 409, 409)


def test_renaming_still_works_once_active(auth_client: TestClient, db: Session) -> None:
    list_id = new_list(auth_client)["id"]
    set_state(db, list_id, "active")

    renamed = auth_client.patch(f"/api/lists/{list_id}", json={"name": "Nume nou"})

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Nume nou"


# Trash


def test_trash_shows_a_deleted_list(auth_client: TestClient, sample: Any) -> None:
    list_id = new_list(auth_client)["id"]
    add_item(auth_client, list_id, size_category_id=sample.size.id, quantity="1")
    auth_client.delete(f"/api/lists/{list_id}")

    trash = auth_client.get("/api/lists/trash")

    assert trash.status_code == 200
    assert [row["id"] for row in trash.json()] == [list_id]
    assert trash.json()[0]["deleted_at"] is not None
    assert len(trash.json()[0]["items"]) == 1


def test_trash_leaves_out_lists_that_are_not_deleted(auth_client: TestClient) -> None:
    new_list(auth_client)

    assert auth_client.get("/api/lists/trash").json() == []


def test_trash_hides_a_list_past_retention(auth_client: TestClient, db: Session) -> None:
    list_id = new_list(auth_client)["id"]
    deleted_ago(db, list_id, get_settings().TRASH_RETENTION_DAYS + 1)

    assert auth_client.get("/api/lists/trash").json() == []


def test_trash_keeps_a_list_inside_retention(auth_client: TestClient, db: Session) -> None:
    list_id = new_list(auth_client)["id"]
    deleted_ago(db, list_id, get_settings().TRASH_RETENTION_DAYS - 1)

    assert [row["id"] for row in auth_client.get("/api/lists/trash").json()] == [list_id]


def test_trash_only_shows_your_own_lists(auth_client: TestClient, other_client: TestClient) -> None:
    list_id = new_list(auth_client)["id"]
    auth_client.delete(f"/api/lists/{list_id}")

    assert other_client.get("/api/lists/trash").json() == []


def test_restore_brings_a_list_back(auth_client: TestClient) -> None:
    list_id = new_list(auth_client)["id"]
    auth_client.delete(f"/api/lists/{list_id}")

    restored = auth_client.post(f"/api/lists/{list_id}/restore")

    assert restored.status_code == 200
    assert restored.json()["id"] == list_id
    assert auth_client.get(f"/api/lists/{list_id}").status_code == 200
    assert auth_client.get("/api/lists/trash").json() == []


def test_restore_past_retention_gives_404(auth_client: TestClient, db: Session) -> None:
    list_id = new_list(auth_client)["id"]
    deleted_ago(db, list_id, get_settings().TRASH_RETENTION_DAYS + 1)

    assert auth_client.post(f"/api/lists/{list_id}/restore").status_code == 404


def test_restore_a_list_that_is_not_deleted_gives_404(auth_client: TestClient) -> None:
    list_id = new_list(auth_client)["id"]

    assert auth_client.post(f"/api/lists/{list_id}/restore").status_code == 404


def test_restore_another_users_list_gives_404(
    auth_client: TestClient, other_client: TestClient
) -> None:
    list_id = new_list(auth_client)["id"]
    auth_client.delete(f"/api/lists/{list_id}")

    assert other_client.post(f"/api/lists/{list_id}/restore").status_code == 404
