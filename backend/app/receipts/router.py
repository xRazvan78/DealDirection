"""Receipt upload, checks and points award. Owner: Member 3, Task 11.

POST /api/lists/{list_id}/receipts?store_id= (multipart field `file`).
POST /api/receipts/read (multipart field `file`) only reads a receipt: nothing
is saved and no points are given, so it needs no list or store.
POST /api/receipts/accept (multipart `file`, `name`, `items`) closes a list kept on
the client's device: it reads the same photo again, so the points come from the
receipt and not from what the client sends, and saves it to a finished list.

Each store's part of an active list takes one receipt. The receipt is read
by the document reader, checked, matched against that part's items, and the
points for the matched items are saved with the receipt in one transaction.

The demo user can use one receipt again and again, so a presenter can repeat the
loop. Its receipts leave no trace of the paper receipt, so they block nobody else.

The cart shows a 422's `detail` to the client as is, so those messages are in
Romanian. A 409 means the receipt (or that part) was already used.
"""

import secrets
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cards.brands import BRANDS
from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.documents.reader import DocumentReader, get_document_reader
from app.documents.schemas import DocumentError, ReceiptData
from app.documents.schemas import ReceiptLine as ReadLineData
from app.models import (
    Category,
    ListItem,
    PointsLedger,
    Receipt,
    ReceiptLine,
    ShoppingList,
    Store,
    StoreProduct,
    User,
)
from app.points.logic import calculate_points
from app.receipts.matching import (
    CENT,
    MatchedLine,
    fingerprint,
    merge_repeated_lines,
    receipt_code,
    score_matches,
)
from app.textutil import fold

router = APIRouter(tags=["receipts"])

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
RECEIPT_TIMEZONE = ZoneInfo("Europe/Bucharest")  # receipts print local time
UNREADABLE = "Nu am putut citi bonul. Fă o poză nouă, cu lumină bună."
NO_MATCH = "Niciun produs de pe bon nu se potrivește cu lista ta."
USED = "Acest bon a fost deja folosit."
DEFAULT_STORE_COLOUR = "#0b2545"
_CODES = ("barcode", "unique_id", "fiscal_key")  # what identifies one paper receipt

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
Reader = Annotated[DocumentReader, Depends(get_document_reader)]


class MatchedItem(BaseModel):
    item_id: int
    name: str
    line: str  # the receipt line it matched, as read
    quantity: Decimal
    line_total: Decimal  # what was paid for the counted quantity
    estimate: Decimal


class UnmatchedItem(BaseModel):
    item_id: int
    name: str


class ReceiptResult(BaseModel):
    matched: list[MatchedItem]
    unmatched_items: list[UnmatchedItem]
    estimate: Decimal
    paid: Decimal
    modifier: Decimal
    points: int
    # Products + deposits matched the printed TOTAL; False suggests a misread line.
    adds_up: bool | None = None


class ReadLine(BaseModel):
    name: str
    quantity: Decimal  # repeated lines are added up, so two bags read as 2
    line_total: Decimal


class ReceiptReading(BaseModel):
    """What a receipt says. A field OCR couldn't read is None."""

    store_name: str | None
    purchased_at: datetime | None
    identifier: str | None  # the barcode if it could be read, else the printed ID
    identifier_printed: bool  # False: none could be read, so the app generated this one
    total: Decimal | None
    deposits: Decimal  # bottle deposits: part of the total, but not products
    lines: list[ReadLine]


class CartItem(BaseModel):
    """A product of a list kept on the client's device."""

    name: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)


class AcceptedReceipt(BaseModel):
    points: int


_CART_ITEMS = TypeAdapter(list[CartItem])


def _reject(code: int, message: str) -> HTTPException:
    return HTTPException(code, detail=message)


def _max_upload_bytes() -> int:
    return get_settings().MAX_UPLOAD_MB * 1024 * 1024


@router.post("/receipts/read")
def read_receipt(file: UploadFile, user: CurrentUser, reader: Reader) -> ReceiptReading:
    content = _read_upload(file)
    try:
        data = reader.read_receipt(content, file.content_type or "")
    except DocumentError:
        raise _reject(422, UNREADABLE) from None
    if not data.lines:
        raise _reject(422, UNREADABLE)

    shown = data.barcode or data.unique_id or data.identifier
    return ReceiptReading(
        store_name=data.store_name or None,
        purchased_at=data.purchased_at,
        identifier=shown or _generated_identifier(data),
        identifier_printed=shown is not None,
        total=data.total,
        deposits=data.deposits,
        lines=[
            ReadLine(name=line.raw_text, quantity=line.quantity, line_total=line.line_total)
            for line in merge_repeated_lines(data.lines)
        ],
    )


@router.post("/lists/{list_id}/receipts")
def upload_receipt(
    list_id: int,
    file: UploadFile,
    user: CurrentUser,
    db: Db,
    reader: Reader,
    store_id: Annotated[int, Query()],
) -> ReceiptResult:
    shopping_list = db.scalars(
        select(ShoppingList).where(
            ShoppingList.id == list_id,
            ShoppingList.user_id == user.id,
            ShoppingList.deleted_at.is_(None),
        )
    ).first()
    if shopping_list is None:
        raise _reject(status.HTTP_404_NOT_FOUND, "Lista nu a fost găsită.")
    store = db.get(Store, store_id)
    if store is None:
        raise _reject(status.HTTP_404_NOT_FOUND, "Magazinul nu a fost găsit.")
    if shopping_list.state == "completed":
        raise _reject(status.HTTP_409_CONFLICT, "Ai scanat deja bonurile pentru această listă.")
    if shopping_list.state != "active":
        raise _reject(status.HTTP_409_CONFLICT, "Alege mai întâi un plan pentru această listă.")

    items = _part_items(db, list_id, store_id)
    if not items:
        raise _reject(422, f"Lista nu are produse de cumpărat de la {store.name}.")
    if _already_used(db, list_id, store_id):
        raise _reject(status.HTTP_409_CONFLICT, f"Ai scanat deja bonul de la {store.name} pentru această listă.")

    content = _read_upload(file)
    try:
        data = reader.read_receipt(content, file.content_type or "")
    except DocumentError:
        raise _reject(422, UNREADABLE) from None
    _check_receipt(data, store)

    purchased_at = data.purchased_at.replace(tzinfo=RECEIPT_TIMEZONE)
    print_ = fingerprint(store.id, purchased_at, data.total)
    if not user.is_demo and _used_before(db, print_, data):
        raise _reject(status.HTTP_409_CONFLICT, USED)

    # The reader matches on expected_price; score_matches prices with estimated_price.
    item_dicts = [
        {
            "id": i.id,
            "name": name,
            "brand": i.brand,
            "expected_price": i.estimated_price,
            "estimated_price": i.estimated_price,
            "quantity": i.quantity,
        }
        for i, name in items
    ]
    lines = merge_repeated_lines(data.lines)  # two bags scanned separately become one line
    matches = reader.match_lines(lines, item_dicts)
    estimate, paid, matched = score_matches(matches, lines, item_dicts)
    if not matched:
        raise _reject(422, NO_MATCH)

    settings = get_settings()
    result = calculate_points(estimate, paid, settings.MARGIN, settings.MAX_MODIFIER, settings.POINTS_PER_LEI)
    modifier = result.modifier.quantize(CENT)

    try:
        _save_receipt(
            db, user, list_id, store, data, print_, lines, estimate, paid, modifier, result.points,
            {m.line_index: m.item_id for m in matched},
        )
        if _every_part_has_a_receipt(db, list_id):
            shopping_list.state = "completed"
        db.commit()
    except IntegrityError:
        # Another upload of the same receipt or part got there first.
        db.rollback()
        raise _reject(status.HTTP_409_CONFLICT, USED) from None

    names = {i.id: name for i, name in items}
    matched_ids = {m.item_id for m in matched}
    return ReceiptResult(
        matched=[
            MatchedItem(
                item_id=m.item_id,
                name=names[m.item_id],
                line=lines[m.line_index].raw_text,
                quantity=m.quantity,
                line_total=m.paid,
                estimate=m.estimate,
            )
            for m in matched
        ],
        unmatched_items=[UnmatchedItem(item_id=i.id, name=name) for i, name in items if i.id not in matched_ids],
        estimate=estimate,
        paid=paid,
        modifier=modifier,
        points=result.points,
        adds_up=data.adds_up,
    )


@router.post("/receipts/accept")
def accept_receipt(
    file: UploadFile,
    name: Annotated[str, Form(min_length=1, max_length=200)],
    items: Annotated[str, Form()],
    user: CurrentUser,
    db: Db,
    reader: Reader,
) -> AcceptedReceipt:
    try:
        cart = _CART_ITEMS.validate_json(items)
    except ValidationError:
        raise _reject(422, "Lista nu a putut fi citită. Verifică produsele și încearcă din nou.") from None

    content = _read_upload(file)
    try:
        data = reader.read_receipt(content, file.content_type or "")
    except DocumentError:
        raise _reject(422, UNREADABLE) from None
    if not data.store_name or data.purchased_at is None or data.total is None or not data.lines:
        raise _reject(422, "Nu am putut citi magazinul, data, totalul sau produsele de pe bon. Fă o poză nouă, cu lumină bună.")

    store = _store_named(db, data.store_name)
    print_ = fingerprint(store.id, data.purchased_at.replace(tzinfo=RECEIPT_TIMEZONE), data.total)
    if not user.is_demo and _used_before(db, print_, data):
        raise _reject(status.HTTP_409_CONFLICT, USED)

    lines = merge_repeated_lines(data.lines)
    estimate, paid, matched = _match_cart(reader, lines, cart)
    # The cart's prices come from the device, so they can't earn more than was really paid.
    estimate = min(estimate, paid)
    settings = get_settings()
    modifier, points = Decimal("1.00"), 0
    if estimate > 0:
        result = calculate_points(estimate, paid, settings.MARGIN, settings.MAX_MODIFIER, settings.POINTS_PER_LEI)
        modifier, points = result.modifier.quantize(CENT), result.points
    points += settings.POINTS_PER_UNLISTED_PRODUCT * (len(lines) - len(matched))
    try:
        shopping_list = ShoppingList(user_id=user.id, name=name, state="completed")
        db.add(shopping_list)
        db.flush()
        _save_receipt(
            db, user, shopping_list.id, store, data, print_, lines, estimate, paid, modifier, points, {},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _reject(status.HTTP_409_CONFLICT, USED) from None
    return AcceptedReceipt(points=points)


def _match_cart(
    reader: DocumentReader, lines: list[ReadLineData], cart: list[CartItem]
) -> tuple[Decimal, Decimal, list[MatchedLine]]:
    """Match the receipt to the cart. A product without a price has no estimate, so it counts as unlisted."""
    item_dicts = [
        {
            "id": index,
            "name": item.name,
            "brand": None,
            "expected_price": item.price,
            "estimated_price": item.price,
            "quantity": item.quantity,
        }
        for index, item in enumerate(cart, start=1)
        if item.price > 0
    ]
    return score_matches(reader.match_lines(lines, item_dicts), lines, item_dicts)


def _store_named(db: Session, name: str) -> Store:
    """The store on a receipt. A real shop we don't compare prices for is added on first use."""
    store = db.scalars(select(Store).where(Store.name == name)).first()
    if store is None:
        colour = next((brand.colour for brand in BRANDS if brand.name == name), DEFAULT_STORE_COLOUR)
        store = Store(name=name, colour=colour)
        db.add(store)
        db.flush()
    return store


def _save_receipt(
    db: Session,
    user: User,
    list_id: int,
    store: Store,
    data: ReceiptData,
    print_: str,
    lines: list[ReadLineData],
    estimate: Decimal,
    paid: Decimal,
    modifier: Decimal,
    points: int,
    matched_by_line: dict[int, int],
) -> None:
    """Add the receipt, its lines and its points. The caller commits."""
    receipt = Receipt(
        list_id=list_id,
        store_id=store.id,
        # A demo receipt keeps none of what identifies the paper one, so it can be used again.
        fingerprint=secrets.token_hex(32) if user.is_demo else print_,
        barcode=None if user.is_demo else data.barcode,
        unique_id=None if user.is_demo else data.unique_id,
        fiscal_key=None if user.is_demo else data.fiscal_key,
        purchased_at=data.purchased_at.replace(tzinfo=RECEIPT_TIMEZONE),
        total=data.total,
        estimate=estimate,
        paid=paid,
        modifier=modifier,
        points=points,
    )
    db.add(receipt)
    db.flush()
    db.add_all(
        ReceiptLine(
            receipt_id=receipt.id,
            raw_text=line.raw_text,
            quantity=line.quantity,
            line_total=line.line_total,
            matched_item_id=matched_by_line.get(index),
        )
        for index, line in enumerate(lines)
    )
    db.add(PointsLedger(user_id=user.id, amount=points, reason=f"Bon {store.name}", receipt_id=receipt.id))
    db.flush()


def _used_before(db: Session, print_: str, data: ReceiptData) -> bool:
    """Has this paper receipt been saved before?

    A scan may read any mix of the barcode, the ID UNIC and the fiscal key, and
    they can't be converted into each other. So a match on any one means the
    same receipt, and a receipt with the same store, day and total is also the
    same one, unless a code read on both scans shows they differ: that's two
    real, identical shops.
    """
    codes = [getattr(Receipt, name) == getattr(data, name) for name in _CODES if getattr(data, name)]
    if codes and db.scalar(select(Receipt.id).where(or_(*codes))) is not None:
        return True

    columns = [getattr(Receipt, name) for name in _CODES]
    similar = db.execute(select(*columns).where(Receipt.fingerprint == print_)).all()
    return any(not _shown_different(row, data) for row in similar)


def _shown_different(row, data: ReceiptData) -> bool:
    return any(
        getattr(row, name) and getattr(data, name) and getattr(row, name) != getattr(data, name) for name in _CODES
    )


def _generated_identifier(data: ReceiptData) -> str | None:
    if not data.store_name or data.purchased_at is None or data.total is None:
        return None
    return receipt_code(data.store_name, data.purchased_at, data.total)


def _part_items(db: Session, list_id: int, store_id: int) -> list[tuple[ListItem, str]]:
    """The list's items assigned to this store, with a name to match against."""
    rows = db.execute(
        select(ListItem, StoreProduct.name, Category.name)
        .outerjoin(StoreProduct, StoreProduct.id == ListItem.assigned_product_id)
        .join(Category, Category.id == ListItem.size_category_id)
        .where(
            ListItem.list_id == list_id,
            ListItem.assigned_store_id == store_id,
            ListItem.removed.is_(False),
        )
        .order_by(ListItem.id)
    ).all()
    return [(item, product_name or category_name) for item, product_name, category_name in rows]


def _already_used(db: Session, list_id: int, store_id: int) -> int | None:
    """The receipt already saved for this part, if any."""
    return db.scalar(select(Receipt.id).where(Receipt.list_id == list_id, Receipt.store_id == store_id))


def _read_upload(file: UploadFile) -> bytes:
    if file.content_type not in IMAGE_TYPES:
        raise _reject(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Trimite o poză JPEG, PNG sau WebP.")
    limit = _max_upload_bytes()
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise _reject(status.HTTP_413_CONTENT_TOO_LARGE, "Poza este prea mare.")
    return content


def _check_receipt(data: ReceiptData, store: Store) -> None:
    if data.purchased_at is None or data.total is None or not data.lines:
        raise _reject(422, "Nu am putut citi data, totalul sau produsele de pe bon. Fă o poză nouă, cu lumină bună.")
    # An unrecognised store reads as "", which every name contains: reject it first.
    if not data.store_name or fold(data.store_name) not in fold(store.name):
        raise _reject(422, f"Bonul nu este de la {store.name}. Scanează bonul de la {store.name}.")


def _every_part_has_a_receipt(db: Session, list_id: int) -> bool:
    parts = db.scalar(
        select(func.count(func.distinct(ListItem.assigned_store_id))).where(
            ListItem.list_id == list_id,
            ListItem.removed.is_(False),
            ListItem.assigned_store_id.is_not(None),
        )
    )
    receipts = db.scalar(select(func.count()).select_from(Receipt).where(Receipt.list_id == list_id))
    return receipts >= parts
