"""List import preview and confirm. Owner: Member 3, Task 12.

POST /api/imports (multipart: `days`, and one of `file` or `text`) reads a
shopping list or nutrition plan, scales it to `days`, and maps each food to a
pack size, for the client to review. POST /api/imports/confirm turns the
reviewed items into a draft shopping list.

A food is first matched to a category *type* by its aliases (sizes of a type
share them), then the best pack size of that type is chosen for the amount.
Where several types share an alias, the one with the most products wins, so
"lapte" means ordinary 3.5% milk rather than a rare kind.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.documents.reader import DocumentReader, get_document_reader
from app.documents.schemas import DocumentError, Food
from app.imports.mapping import Size, choose_size, scale_foods
from app.models import Category, ListItem, ShoppingList, StoreProduct, User

router = APIRouter(tags=["imports"])

FILE_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_DAYS = 366

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
Reader = Annotated[DocumentReader, Depends(get_document_reader)]


class ImportItem(BaseModel):
    food: str
    size_category_id: int
    path: str
    packs: int


class ImportPreview(BaseModel):
    items: list[ImportItem]
    unmapped: list[str]


class ConfirmItem(BaseModel):
    size_category_id: int
    packs: int = Field(gt=0, le=999)


class ImportConfirmation(BaseModel):
    name: str = Field(max_length=200)
    items: list[ConfirmItem] = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def name_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Give the list a name")
        return value.strip()


class CreatedList(BaseModel):
    list_id: int


@dataclass
class _Type:
    """A category type with its sizes, as candidates for one food."""

    id: int
    category: str
    name: str
    path_prefix: str  # "Group > Category > Type"
    aliases: list[str] = field(default_factory=list)
    sizes: list[Size] = field(default_factory=list)
    size_names: dict[int, str] = field(default_factory=dict)
    products: int = 0


def _max_upload_bytes() -> int:
    return get_settings().MAX_UPLOAD_MB * 1024 * 1024


@router.post("/imports")
def preview_import(
    user: CurrentUser,
    db: Db,
    reader: Reader,
    days: Annotated[int, Form(gt=0, le=MAX_DAYS)],
    file: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
) -> ImportPreview:
    has_text = bool(text and text.strip())
    if (file is None) == (not has_text):
        raise HTTPException(422, detail="Trimite fie un fișier, fie un text, nu pe amândouă.")

    try:
        if file is not None:
            food_list = reader.read_foods(_read_upload(file), file.content_type or "")
        else:
            food_list = reader.read_foods(text.encode("utf-8"), "text/plain")
    except DocumentError:
        raise HTTPException(422, detail="Nu am putut citi lista. Încearcă din nou sau lipește textul.") from None

    scaled = scale_foods(food_list, days)
    if not scaled:
        raise HTTPException(
            422, detail="Nu am găsit alimente cu cantități, de exemplu „200 g piept de pui zilnic”. Încearcă din nou sau lipește textul."
        )

    types = _catalog_types(db)
    by_id = {t.id: t for t in types}
    leaves = [{"id": t.id, "path": [t.category, t.name], "aliases": t.aliases} for t in types]
    mappings = reader.map_foods(
        [Food(name=f.name, amount=f.amount, unit=f.unit, per_day=False) for f in scaled], leaves
    )

    items: list[ImportItem] = []
    unmapped: list[str] = []
    for food, mapping in zip(scaled, mappings):
        kind = by_id.get(mapping.size_category_id) if mapping.size_category_id is not None else None
        choice = choose_size(food.amount, food.unit, kind.sizes) if kind else None
        if choice is None:
            unmapped.append(food.name)  # unknown food, or no size in its unit
            continue
        size_id, packs = choice
        items.append(
            ImportItem(food=food.name, size_category_id=size_id, path=f"{kind.path_prefix} > {kind.size_names[size_id]}", packs=packs)
        )
    return ImportPreview(items=items, unmapped=unmapped)


@router.post("/imports/confirm", status_code=status.HTTP_201_CREATED)
def confirm_import(confirmation: ImportConfirmation, user: CurrentUser, db: Db) -> CreatedList:
    packs: dict[int, int] = {}
    for item in confirmation.items:  # the same size twice adds up, as when adding to a list
        packs[item.size_category_id] = packs.get(item.size_category_id, 0) + item.packs

    valid = set(db.scalars(select(Category.id).where(Category.id.in_(packs), Category.level == "size")))
    if valid != set(packs):
        raise HTTPException(422, detail="Unele produse nu mai există în catalog. Reîncarcă lista.")

    shopping_list = ShoppingList(user_id=user.id, name=confirmation.name, state="draft")
    db.add(shopping_list)
    db.flush()
    db.add_all(ListItem(list_id=shopping_list.id, size_category_id=size_id, quantity=count) for size_id, count in packs.items())
    db.commit()
    return CreatedList(list_id=shopping_list.id)


def _read_upload(file: UploadFile) -> bytes:
    if file.content_type not in FILE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Trimite un PDF sau o poză JPEG, PNG ori WebP.")
    limit = _max_upload_bytes()
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="Fișierul este prea mare.")
    return content


def _catalog_types(db: Session) -> Sequence[_Type]:
    """Every category type that has sizes, the most stocked first."""
    size, kind, category, group = (aliased(Category) for _ in range(4))
    rows = db.execute(
        select(size.id, size.name, size.size_amount, size.size_unit, size.aliases, kind.id, kind.name, category.name, group.name)
        .join(kind, kind.id == size.parent_id)
        .join(category, category.id == kind.parent_id)
        .outerjoin(group, group.id == category.parent_id)
        .where(size.level == "size", size.size_amount.is_not(None), size.size_unit.is_not(None))
        .order_by(size.id)
    ).all()
    counts = dict(
        db.execute(select(StoreProduct.type_category_id, func.count()).group_by(StoreProduct.type_category_id)).all()
    )

    types: dict[int, _Type] = {}
    for size_id, size_name, amount, unit, aliases, kind_id, kind_name, category_name, group_name in rows:
        entry = types.get(kind_id)
        if entry is None:
            prefix = " > ".join(name for name in (group_name, category_name, kind_name) if name)
            entry = types[kind_id] = _Type(kind_id, category_name, kind_name, prefix, products=counts.get(kind_id, 0))
        entry.sizes.append(Size(size_id, amount, unit))
        entry.size_names[size_id] = size_name
        entry.aliases.extend(a for a in aliases or [] if a not in entry.aliases)
    return sorted(types.values(), key=lambda t: (-t.products, t.id))
