"""Loyalty cards: scan a card's code, save it under a brand, show it at the till.

Flow on the Cards screen:
1. POST /api/cards/scan with a photo reads the QR code or barcode and suggests
   a brand from the card's printed text or the code. Nothing is saved.
2. POST /api/cards saves the code under the brand the client picked. If no
   code could be read, the photo itself can be saved instead, as a fallback.
3. GET /api/cards returns each card with its code redrawn as a clean SVG.
4. DELETE /api/cards/{id}. A brand holds one card, so replacing a card means
   deleting it first.

Error `detail` texts are in Romanian, for the client.
"""

import base64
from typing import Annotated

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cards.brands import BRANDS, brand_by_id
from app.cards.codes import CodeError, decode, draw_svg, guess_brand
from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.documents.ocr import image_to_text
from app.documents.schemas import DocumentError
from app.models import LoyaltyCard, User

router = APIRouter(tags=["cards"])

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
PHOTO_MAX_SIDE = 1000  # px: plenty for a till to read, small to store

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


class BrandOut(BaseModel):
    id: str
    name: str
    colour: str


class ScanResult(BaseModel):
    code_text: str
    code_format: str
    image: str  # data URI of the redrawn code
    suggested_brand: str | None


class CardOut(BaseModel):
    id: int
    brand: str
    name: str
    colour: str
    code_text: str | None
    code_format: str | None
    image: str  # data URI: the redrawn code, or the saved photo


def _max_upload_bytes() -> int:
    return get_settings().MAX_UPLOAD_MB * 1024 * 1024


def _printed_text(content: bytes) -> str:
    """The card's printed text, to spot the brand name. Empty if it can't be read."""
    try:
        return image_to_text(content, get_settings())
    except DocumentError:
        return ""


@router.get("/card-brands")
def list_brands() -> list[BrandOut]:
    return [BrandOut(id=b.id, name=b.name, colour=b.colour) for b in BRANDS]


@router.post("/cards/scan")
def scan_card(file: UploadFile, user: CurrentUser) -> ScanResult:
    content = _read_photo(file)
    try:
        code = decode(content)
    except CodeError:
        raise HTTPException(422, detail="Nu am putut deschide poza. Încearcă altă poză.") from None
    if code is None:
        raise HTTPException(
            422,
            detail="Nu am găsit niciun cod QR sau cod de bare. Fă o poză mai de aproape, cu codul întreg și clar.",
        )
    return ScanResult(
        code_text=code.text,
        code_format=code.format,
        image=_svg_uri(draw_svg(code.text, code.format)),
        suggested_brand=guess_brand(code.text, _printed_text(content)),
    )


@router.post("/cards", status_code=status.HTTP_201_CREATED)
def save_card(
    user: CurrentUser,
    db: Db,
    brand: Annotated[str, Form()],
    code_text: Annotated[str | None, Form()] = None,
    code_format: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> CardOut:
    chosen = brand_by_id(brand)
    if chosen is None:
        raise HTTPException(422, detail="Alege magazinul cardului din listă.")
    has_code = bool(code_text) and bool(code_format)
    if has_code == (file is not None) or (not has_code and (code_text or code_format)):
        raise HTTPException(422, detail="Trimite fie codul scanat, fie poza cardului.")

    card = LoyaltyCard(user_id=user.id, brand=chosen.id)
    if has_code:
        try:
            draw_svg(code_text, code_format)  # proves the code is valid and drawable
        except CodeError:
            raise HTTPException(422, detail="Codul cardului nu este valid. Scanează-l din nou.") from None
        card.code_text, card.code_format = code_text, code_format
    else:
        card.photo = _shrink(_read_photo(file))

    db.add(card)
    try:
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Ai deja un card {chosen.name}. Șterge-l mai întâi ca să-l înlocuiești.",
        ) from None
    return _card_out(card)


@router.get("/cards")
def list_cards(user: CurrentUser, db: Db) -> list[CardOut]:
    cards = db.scalars(select(LoyaltyCard).where(LoyaltyCard.user_id == user.id).order_by(LoyaltyCard.id))
    return [_card_out(card) for card in cards]


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: int, user: CurrentUser, db: Db) -> Response:
    card = db.get(LoyaltyCard, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Cardul nu a fost găsit.")
    db.delete(card)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _read_photo(file: UploadFile) -> bytes:
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Trimite o poză JPEG, PNG sau WebP.")
    limit = _max_upload_bytes()
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="Poza este prea mare.")
    return content


def _shrink(content: bytes) -> bytes:
    """The photo as a JPEG no larger than PHOTO_MAX_SIDE on its longest side."""
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(422, detail="Nu am putut deschide poza. Încearcă altă poză.")
    scale = min(1.0, PHOTO_MAX_SIDE / max(image.shape[:2]))
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return encoded.tobytes()


def _svg_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _card_out(card: LoyaltyCard) -> CardOut:
    brand = brand_by_id(card.brand)
    if card.code_text and card.code_format:
        image = _svg_uri(draw_svg(card.code_text, card.code_format))
    else:
        image = "data:image/jpeg;base64," + base64.b64encode(card.photo or b"").decode()
    return CardOut(
        id=card.id,
        brand=card.brand,
        name=brand.name if brand else card.brand,
        colour=brand.colour if brand else "#555555",
        code_text=card.code_text,
        code_format=card.code_format,
        image=image,
    )
