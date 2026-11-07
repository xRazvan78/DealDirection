"""Receipt upload, checks and points award. Owner: Member 3, Task 11.

POST /api/lists/{list_id}/receipts?store_id= (multipart field `file`).

Each store's part of an active list takes one receipt. The receipt is read
by the document reader, checked, matched against that part's items, and the
points for the matched items are saved with the receipt in one transaction.

The cart shows a 422's `detail` to the client as is, so those messages are in
Romanian. A 409 means the receipt (or that part) was already used.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.documents.reader import DocumentReader, get_document_reader
from app.documents.schemas import DocumentError, ReceiptData
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
from app.receipts.matching import CENT, fingerprint, merge_repeated_lines, score_matches
from app.textutil import fold

router = APIRouter(tags=["receipts"])

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
RECEIPT_TIMEZONE = ZoneInfo("Europe/Bucharest")  # receipts print local time

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


def _reject(code: int, message: str) -> HTTPException:
    return HTTPException(code, detail=message)


def _max_upload_bytes() -> int:
    return get_settings().MAX_UPLOAD_MB * 1024 * 1024


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
        raise _reject(422, "Nu am putut citi bonul. Fă o poză nouă, cu lumină bună.") from None
    _check_receipt(data, store)

    purchased_at = data.purchased_at.replace(tzinfo=RECEIPT_TIMEZONE)
    print_ = fingerprint(store.id, purchased_at, data.total, data.fiscal_key)
    if db.scalar(select(Receipt.id).where(Receipt.fingerprint == print_)) is not None:
        raise _reject(status.HTTP_409_CONFLICT, "Acest bon a fost deja folosit.")

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
        raise _reject(422, "Niciun produs de pe bon nu se potrivește cu lista ta.")

    settings = get_settings()
    result = calculate_points(estimate, paid, settings.MARGIN, settings.MAX_MODIFIER, settings.POINTS_PER_LEI)
    modifier = result.modifier.quantize(CENT)

    receipt = Receipt(
        list_id=list_id,
        store_id=store.id,
        fingerprint=print_,
        purchased_at=purchased_at,
        total=data.total,
        estimate=estimate,
        paid=paid,
        modifier=modifier,
        points=result.points,
    )
    try:
        db.add(receipt)
        db.flush()
        matched_by_line = {m.line_index: m.item_id for m in matched}
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
        db.add(PointsLedger(user_id=user.id, amount=result.points, reason=f"Bon {store.name}", receipt_id=receipt.id))
        db.flush()
        if _every_part_has_a_receipt(db, list_id):
            shopping_list.state = "completed"
        db.commit()
    except IntegrityError:
        # Another upload of the same receipt or part got there first.
        db.rollback()
        raise _reject(status.HTTP_409_CONFLICT, "Acest bon a fost deja folosit.") from None

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
