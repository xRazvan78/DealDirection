"""Loyalty card routes, with the real database rolled back after each test.

Flow: POST /api/cards/scan reads the code from a photo and suggests a brand
(nothing saved); POST /api/cards saves it under the chosen brand. One card
per brand: replacing one means deleting it first.
"""

import base64
import io

import pytest
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cards import router as cards_router
from app.deps import create_token
from app.main import app
from app.models import LoyaltyCard, User
from tests.backend.test_card_codes import QR_TEXT, code_photo

EAN13_TEXT = "2401234567891"


@pytest.fixture(autouse=True)
def no_printed_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip OCR of the card's printed text; tests that need it set their own."""
    monkeypatch.setattr(cards_router, "_printed_text", lambda content: "")


@pytest.fixture
def owner(client: TestClient, db: Session) -> tuple[TestClient, User]:
    user = User(email="cards-owner@example.com", password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    return TestClient(app, headers={"Authorization": f"Bearer {create_token(user)}"}), user


def jpeg(text: str = QR_TEXT, fmt=zxingcpp.BarcodeFormat.QRCode):
    return ("card.jpg", code_photo(text, fmt), "image/jpeg")


def blank_photo():
    buffer = io.BytesIO()
    Image.new("RGB", (640, 400), (230, 230, 230)).save(buffer, "JPEG")
    return ("card.jpg", buffer.getvalue(), "image/jpeg")


def save(client: TestClient, brand: str = "lidl", text: str = QR_TEXT, fmt: str = "qr", file=None):
    data = {"brand": brand}
    if file is None:
        data.update(code_text=text, code_format=fmt)
    return client.post("/api/cards", data=data, files={"file": file} if file else None)


def cards_of(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(LoyaltyCard).where(LoyaltyCard.user_id == user.id))


# --- Brands -----------------------------------------------------------------


def test_brands_are_listed(owner) -> None:
    client, _ = owner

    body = client.get("/api/card-brands").json()

    assert body[0] == {"id": "lidl", "name": "Lidl", "colour": "#0050aa"}
    assert [b["id"] for b in body] == ["lidl", "kaufland", "auchan", "carrefour", "mega-image", "profi", "penny"]


# --- Scan -------------------------------------------------------------------


def test_scan_reads_a_qr_code_and_saves_nothing(db: Session, owner) -> None:
    client, user = owner

    response = client.post("/api/cards/scan", files={"file": jpeg()})

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["code_text"], body["code_format"], body["suggested_brand"]) == (QR_TEXT, "qr", None)
    assert body["image"].startswith("data:image/svg+xml;base64,")
    assert "<svg" in base64.b64decode(body["image"].split(",", 1)[1]).decode()
    assert cards_of(db, user) == 0


def test_scan_reads_a_barcode(owner) -> None:
    client, _ = owner

    body = client.post("/api/cards/scan", files={"file": jpeg(EAN13_TEXT, zxingcpp.BarcodeFormat.EAN13)}).json()

    assert (body["code_text"], body["code_format"]) == (EAN13_TEXT, "ean13")


def test_scan_suggests_the_brand_printed_on_the_card(owner, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = owner
    monkeypatch.setattr(cards_router, "_printed_text", lambda content: "KAUFLAND Card")

    assert client.post("/api/cards/scan", files={"file": jpeg()}).json()["suggested_brand"] == "kaufland"


def test_scan_without_a_code_explains_what_to_do(owner) -> None:
    client, _ = owner

    response = client.post("/api/cards/scan", files={"file": blank_photo()})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize(
    ("file", "code"),
    [(("card.pdf", b"%PDF", "application/pdf"), 415), (("card.jpg", b"not an image", "image/jpeg"), 422)],
    ids=["wrong type", "unreadable"],
)
def test_scan_rejects_bad_files(owner, file, code) -> None:
    client, _ = owner

    assert client.post("/api/cards/scan", files={"file": file}).status_code == code


def test_scan_rejects_an_oversized_file(owner, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = owner
    monkeypatch.setattr(cards_router, "_max_upload_bytes", lambda: 10)

    assert client.post("/api/cards/scan", files={"file": jpeg()}).status_code == 413


# --- Save -------------------------------------------------------------------


def test_save_a_scanned_code(db: Session, owner) -> None:
    client, user = owner

    response = save(client, "lidl", QR_TEXT, "qr")

    assert response.status_code == 201, response.text
    body = response.json()
    assert {k: body[k] for k in ("brand", "name", "colour", "code_text", "code_format")} == {
        "brand": "lidl", "name": "Lidl", "colour": "#0050aa", "code_text": QR_TEXT, "code_format": "qr",
    }
    assert body["image"].startswith("data:image/svg+xml;base64,")
    saved = db.scalars(select(LoyaltyCard).where(LoyaltyCard.user_id == user.id)).one()
    assert (saved.brand, saved.code_text, saved.photo) == ("lidl", QR_TEXT, None)


def test_one_card_per_brand(db: Session, owner) -> None:
    client, user = owner
    assert save(client, "auchan", EAN13_TEXT, "ean13").status_code == 201

    response = save(client, "auchan", "96385074", "ean8")

    assert response.status_code == 409
    assert "Auchan" in response.json()["detail"]
    assert cards_of(db, user) == 1


def test_save_rejects_an_unknown_brand(owner) -> None:
    client, _ = owner

    assert save(client, "megamart").status_code == 422


def test_save_rejects_an_invalid_code(owner) -> None:
    client, _ = owner

    assert save(client, "lidl", "2401234567893", "ean13").status_code == 422  # wrong check digit
    assert save(client, "lidl", "123", "datamatrix").status_code == 422


def test_save_photo_when_no_code_could_be_read(db: Session, owner) -> None:
    client, user = owner

    response = save(client, "penny", file=blank_photo())

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["code_text"], body["code_format"]) == (None, None)
    assert body["image"].startswith("data:image/jpeg;base64,")
    saved = db.scalars(select(LoyaltyCard).where(LoyaltyCard.user_id == user.id)).one()
    assert saved.photo is not None


def test_saved_photo_is_shrunk(db: Session, owner) -> None:
    client, user = owner
    buffer = io.BytesIO()
    Image.new("RGB", (3000, 2000), (200, 200, 200)).save(buffer, "JPEG")

    save(client, "profi", file=("big.jpg", buffer.getvalue(), "image/jpeg"))

    photo = db.scalars(select(LoyaltyCard.photo).where(LoyaltyCard.user_id == user.id)).one()
    assert max(Image.open(io.BytesIO(photo)).size) == 1000


@pytest.mark.parametrize(
    "data",
    [{"brand": "lidl"}, {"brand": "lidl", "code_text": QR_TEXT}, {"brand": "lidl", "code_format": "qr"}],
    ids=["nothing", "text only", "format only"],
)
def test_save_needs_a_code_or_a_photo(owner, data) -> None:
    client, _ = owner

    assert client.post("/api/cards", data=data).status_code == 422


def test_save_rejects_both_a_code_and_a_photo(owner) -> None:
    client, _ = owner

    response = client.post("/api/cards", data={"brand": "lidl", "code_text": QR_TEXT, "code_format": "qr"}, files={"file": blank_photo()})

    assert response.status_code == 422


# --- List and delete --------------------------------------------------------


def test_list_shows_only_my_cards(db: Session, owner, other_client: TestClient) -> None:
    client, _ = owner
    save(client, "lidl", QR_TEXT, "qr")
    save(client, "kaufland", EAN13_TEXT, "ean13")
    save(other_client, "penny", "96385074", "ean8")

    body = client.get("/api/cards").json()

    assert [(c["brand"], c["name"]) for c in body] == [("lidl", "Lidl"), ("kaufland", "Kaufland")]
    assert all(c["image"].startswith("data:image/") for c in body)


def test_delete_frees_the_brand_for_a_new_card(db: Session, owner) -> None:
    client, user = owner
    card_id = save(client, "lidl", QR_TEXT, "qr").json()["id"]

    assert client.delete(f"/api/cards/{card_id}").status_code == 204
    assert cards_of(db, user) == 0
    assert save(client, "lidl", EAN13_TEXT, "ean13").status_code == 201


def test_cannot_delete_another_users_card(db: Session, owner, other_client: TestClient) -> None:
    client, user = owner
    card_id = save(client, "lidl", QR_TEXT, "qr").json()["id"]

    assert other_client.delete(f"/api/cards/{card_id}").status_code == 404
    assert cards_of(db, user) == 1


def test_delete_unknown_card(owner) -> None:
    client, _ = owner

    assert client.delete("/api/cards/999999999").status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/cards"), ("post", "/api/cards"), ("post", "/api/cards/scan"), ("delete", "/api/cards/1")],
)
def test_login_is_required(client: TestClient, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 401
