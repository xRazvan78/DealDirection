"""Saved lists: the same lists on every device of one client."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import create_token
from app.main import app
from app.models import User

ITEMS = [{"name": "Mere", "quantity": "2", "price": "5"}]
EARLY = "2026-11-07T10:00:00Z"
LATE = "2026-11-07T11:00:00Z"


def saved(client: TestClient) -> list[dict]:
    return client.get("/api/saved-lists").json()


def put(client: TestClient, list_id: int = 1, **details):
    body = {"name": "Prima", "items": ITEMS, "updated_at": EARLY} | details
    return client.put(f"/api/saved-lists/{list_id}", json=body)


def test_a_list_saved_on_one_device_shows_on_another(auth_client: TestClient) -> None:
    assert put(auth_client).status_code == 200

    other_device = TestClient(app, headers=dict(auth_client.headers))

    assert [(row["id"], row["name"], row["items"]) for row in saved(other_device)] == [(1, "Prima", ITEMS)]


def test_item_keys_keep_their_order(auth_client: TestClient) -> None:
    item = {"quantity": "1", "id": 1, "name": "Mere", "storeId": None}

    put(auth_client, items=[item])

    assert list(saved(auth_client)[0]["items"][0]) == list(item)


def test_a_newer_save_replaces_the_list(auth_client: TestClient) -> None:
    put(auth_client)

    put(auth_client, name="Nouă", updated_at=LATE)

    assert [row["name"] for row in saved(auth_client)] == ["Nouă"]


def test_an_older_save_arriving_late_is_ignored(auth_client: TestClient) -> None:
    put(auth_client, name="Nouă", updated_at=LATE)

    response = put(auth_client, name="Veche", updated_at=EARLY)

    assert response.json()["name"] == "Nouă"


def test_a_list_with_a_receipt_can_no_longer_change(auth_client: TestClient) -> None:
    put(auth_client, receipt={"store_name": "Kaufland"}, points=120)

    response = put(auth_client, name="Altă listă", updated_at=LATE)

    assert response.json()["name"] == "Prima"
    assert response.json()["receipt"] == {"store_name": "Kaufland"}
    assert response.json()["points"] == 120


def test_a_list_without_a_receipt_stays_without_one(auth_client: TestClient) -> None:
    put(auth_client)

    assert saved(auth_client)[0]["receipt"] is None
    assert put(auth_client, receipt={"store_name": "Kaufland"}, updated_at=EARLY).json()["receipt"] is not None


def test_a_deleted_list_is_gone_everywhere(auth_client: TestClient) -> None:
    put(auth_client)

    assert auth_client.delete("/api/saved-lists/1").status_code == 204

    assert saved(auth_client) == []


def test_another_client_sees_and_changes_nothing(auth_client: TestClient, db: Session) -> None:
    put(auth_client)
    stranger = User(email="stranger@example.com", password_hash="not-a-real-hash")
    db.add(stranger)
    db.flush()
    other = TestClient(app, headers={"Authorization": f"Bearer {create_token(stranger)}"})

    assert saved(other) == []
    other.delete("/api/saved-lists/1")
    assert put(other, name="A lui").json()["name"] == "A lui"

    assert [row["name"] for row in saved(auth_client)] == ["Prima"]


def test_login_is_required(client: TestClient) -> None:
    assert client.get("/api/saved-lists").status_code == 401
    assert put(client).status_code == 401
