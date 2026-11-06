"""Shopping lists and list items. Owner: Member 2, Task 8."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.models import Category, ListItem, ShoppingList, StoreProduct, User

MAX_QUANTITY = Decimal("9999")

router = APIRouter(tags=["lists"])

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
ListName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Quantity = Annotated[Decimal, Field(gt=0, le=MAX_QUANTITY, decimal_places=3)]


class ListIn(BaseModel):
    name: ListName


class NewItem(BaseModel):
    size_category_id: int
    quantity: Quantity
    chosen_product_id: int | None = None


class ItemQuantity(BaseModel):
    quantity: Quantity


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    size_category_id: int
    chosen_product_id: int | None
    brand: str | None
    quantity: Decimal
    removed: bool


class ListOut(BaseModel):
    id: int
    name: str
    state: Literal["draft", "active", "completed"]
    items: list[ItemOut]


class TrashedListOut(ListOut):
    deleted_at: datetime


def _trash_filter(user: User) -> list[ColumnElement[bool]]:
    """Deleted lists the client can still see: older ones are hidden for good."""
    retention = timedelta(days=get_settings().TRASH_RETENTION_DAYS)
    return [
        ShoppingList.user_id == user.id,
        ShoppingList.deleted_at.is_not(None),
        ShoppingList.deleted_at >= datetime.now(UTC) - retention,
    ]


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="List not found")


def _owned_list(db: Session, user: User, list_id: int) -> ShoppingList:
    """The client's list, or 404 so nobody learns which ids other clients have."""
    shopping_list = db.scalars(
        select(ShoppingList).where(
            ShoppingList.id == list_id,
            ShoppingList.user_id == user.id,
            ShoppingList.deleted_at.is_(None),
        )
    ).first()
    if shopping_list is None:
        raise _not_found()
    return shopping_list


def _editable_list(db: Session, user: User, list_id: int) -> ShoppingList:
    """Plans store each item's store and price, so only drafts can change items."""
    shopping_list = _owned_list(db, user, list_id)
    if shopping_list.state != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This list is locked")
    return shopping_list


def _list_item(db: Session, list_id: int, item_id: int) -> ListItem:
    item = db.get(ListItem, item_id)
    if item is None or item.list_id != list_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


def _items_by_list(db: Session, list_ids: Sequence[int]) -> dict[int, list[ListItem]]:
    items: dict[int, list[ListItem]] = defaultdict(list)
    rows = db.scalars(
        select(ListItem).where(ListItem.list_id.in_(list_ids)).order_by(ListItem.id)
    )
    for item in rows:
        items[item.list_id].append(item)
    return items


def _fields(shopping_list: ShoppingList, items: Sequence[ListItem]) -> dict[str, Any]:
    return {
        "id": shopping_list.id,
        "name": shopping_list.name,
        "state": shopping_list.state,
        "items": [ItemOut.model_validate(item) for item in items],
    }


def _list_out(db: Session, shopping_list: ShoppingList) -> ListOut:
    items = _items_by_list(db, [shopping_list.id])[shopping_list.id]
    return ListOut(**_fields(shopping_list, items))


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _check_new_item(db: Session, new: NewItem) -> StoreProduct | None:
    """Returns the chosen product, once the item's ids are known to fit together."""
    category = db.get(Category, new.size_category_id)
    if category is None or category.level != "size":
        raise _invalid("Unknown size category")
    if new.chosen_product_id is None:
        return None
    product = db.get(StoreProduct, new.chosen_product_id)
    if product is None or product.size_category_id != category.id:
        raise _invalid("Unknown product for this size")
    return product


# Lists


@router.post("/lists", status_code=status.HTTP_201_CREATED)
def create_list(body: ListIn, user: CurrentUser, db: Db) -> ListOut:
    shopping_list = ShoppingList(user_id=user.id, name=body.name)
    db.add(shopping_list)
    db.commit()
    db.refresh(shopping_list)
    return _list_out(db, shopping_list)


@router.get("/lists")
def get_lists(user: CurrentUser, db: Db) -> list[ListOut]:
    lists = db.scalars(
        select(ShoppingList)
        .where(ShoppingList.user_id == user.id, ShoppingList.deleted_at.is_(None))
        .order_by(ShoppingList.created_at.desc(), ShoppingList.id.desc())
    ).all()
    items = _items_by_list(db, [row.id for row in lists])
    return [ListOut(**_fields(row, items[row.id])) for row in lists]


# Declared before /lists/{list_id}, so "trash" isn't read as a list id.
@router.get("/lists/trash")
def get_trash(user: CurrentUser, db: Db) -> list[TrashedListOut]:
    lists = db.scalars(
        select(ShoppingList)
        .where(*_trash_filter(user))
        .order_by(ShoppingList.deleted_at.desc(), ShoppingList.id.desc())
    ).all()
    items = _items_by_list(db, [row.id for row in lists])
    return [
        TrashedListOut(**_fields(row, items[row.id]), deleted_at=row.deleted_at)
        for row in lists
    ]


@router.get("/lists/{list_id}")
def get_list(list_id: int, user: CurrentUser, db: Db) -> ListOut:
    return _list_out(db, _owned_list(db, user, list_id))


@router.patch("/lists/{list_id}")
def rename_list(list_id: int, body: ListIn, user: CurrentUser, db: Db) -> ListOut:
    shopping_list = _owned_list(db, user, list_id)
    shopping_list.name = body.name
    db.commit()
    return _list_out(db, shopping_list)


@router.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(list_id: int, user: CurrentUser, db: Db) -> None:
    _owned_list(db, user, list_id).deleted_at = datetime.now(UTC)
    db.commit()


@router.post("/lists/{list_id}/restore")
def restore_list(list_id: int, user: CurrentUser, db: Db) -> ListOut:
    shopping_list = db.scalars(
        select(ShoppingList).where(ShoppingList.id == list_id, *_trash_filter(user))
    ).first()
    if shopping_list is None:
        raise _not_found()
    shopping_list.deleted_at = None
    db.commit()
    return _list_out(db, shopping_list)


@router.post("/lists/{list_id}/complete")
def complete_list(list_id: int, user: CurrentUser, db: Db) -> ListOut:
    shopping_list = _owned_list(db, user, list_id)
    shopping_list.state = "completed"
    db.commit()
    return _list_out(db, shopping_list)


# List items


@router.post("/lists/{list_id}/items", status_code=status.HTTP_201_CREATED)
def add_item(list_id: int, body: NewItem, user: CurrentUser, db: Db) -> ItemOut:
    _editable_list(db, user, list_id)
    product = _check_new_item(db, body)

    item = db.scalars(
        select(ListItem).where(
            ListItem.list_id == list_id,
            ListItem.size_category_id == body.size_category_id,
            ListItem.chosen_product_id.is_not_distinct_from(body.chosen_product_id),
        )
    ).first()
    if item is None:
        item = ListItem(
            list_id=list_id,
            size_category_id=body.size_category_id,
            chosen_product_id=body.chosen_product_id,
            brand=product.brand if product else None,
            quantity=body.quantity,
        )
        db.add(item)
    elif item.quantity + body.quantity > MAX_QUANTITY:
        raise _invalid("Quantity is too large")
    else:
        item.quantity += body.quantity
    db.commit()
    db.refresh(item)
    return ItemOut.model_validate(item)


@router.patch("/lists/{list_id}/items/{item_id}")
def update_item(
    list_id: int, item_id: int, body: ItemQuantity, user: CurrentUser, db: Db
) -> ItemOut:
    _editable_list(db, user, list_id)
    item = _list_item(db, list_id, item_id)
    item.quantity = body.quantity
    db.commit()
    db.refresh(item)
    return ItemOut.model_validate(item)


@router.delete("/lists/{list_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(list_id: int, item_id: int, user: CurrentUser, db: Db) -> None:
    _editable_list(db, user, list_id)
    db.delete(_list_item(db, list_id, item_id))
    db.commit()
