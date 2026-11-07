"""Saved lists, so a client sees the same lists on every device.

The device makes each list's id, and sends the whole list whenever it changes.
A list with a receipt is finished, so a later save from another device can't
change it. Otherwise the newest save wins, even if saves arrive out of order.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import SavedList, User

MAX_ID = 2**53  # the largest whole number JavaScript counts exactly

router = APIRouter(tags=["saved lists"])

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
ListId = Annotated[int, Path(gt=0, le=MAX_ID)]


class SavedListIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    items: list[dict[str, Any]]
    updated_at: datetime
    receipt: dict[str, Any] | None = None
    points: int | None = None


class SavedListOut(SavedListIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


@router.get("/saved-lists")
def get_saved_lists(user: CurrentUser, db: Db) -> list[SavedListOut]:
    rows = db.scalars(
        select(SavedList).where(SavedList.user_id == user.id).order_by(SavedList.updated_at.desc())
    )
    return [SavedListOut.model_validate(row) for row in rows]


@router.put("/saved-lists/{list_id}")
def save_list(list_id: ListId, details: SavedListIn, user: CurrentUser, db: Db) -> SavedListOut:
    """Returns the list as stored, which may be a newer or finished version."""
    values = details.model_dump()
    db.execute(
        insert(SavedList)
        .values(user_id=user.id, id=list_id, **values)
        .on_conflict_do_update(
            index_elements=[SavedList.user_id, SavedList.id],
            set_=values,
            where=and_(SavedList.receipt.is_(None), SavedList.updated_at <= details.updated_at),
        )
    )
    db.commit()
    return SavedListOut.model_validate(db.get(SavedList, (user.id, list_id), populate_existing=True))


@router.delete("/saved-lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_list(list_id: ListId, user: CurrentUser, db: Db) -> None:
    db.execute(delete(SavedList).where(SavedList.user_id == user.id, SavedList.id == list_id))
    db.commit()
