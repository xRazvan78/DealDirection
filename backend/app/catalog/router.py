"""Stores, store selection, categories, products and search. Owner: Member 2, Task 7."""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Category, Store, StoreProduct, User, UserStore
from app.textutil import fold

MAX_SEARCH_RESULTS = 50

router = APIRouter(tags=["catalog"])

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


class StoreOut(BaseModel):
    id: int
    name: str
    colour: str
    logo: str | None
    selected: bool


class StoreSelection(BaseModel):
    store_ids: list[int]


class CategoryOut(BaseModel):
    id: int
    parent_id: int | None
    name: str
    level: str


class ProductOut(BaseModel):
    id: int
    store_id: int
    store_name: str
    name: str
    brand: str | None
    price: Decimal
    image_url: str | None
    updated_at: datetime


class CategoryProducts(BaseModel):
    generic: ProductOut | None
    products: list[ProductOut]


class SearchResult(BaseModel):
    size_category_id: int
    path: str
    generic: ProductOut | None


def selected_store_ids(db: Session, user: User) -> set[int]:
    return set(db.scalars(select(UserStore.store_id).where(UserStore.user_id == user.id)))


def offers(
    db: Session, user: User, size_category_ids: Iterable[int]
) -> list[tuple[StoreProduct, str]]:
    """Return these sizes' products at the user's stores with store names, cheapest first."""
    rows = db.execute(
        select(StoreProduct, Store.name)
        .join(Store, Store.id == StoreProduct.store_id)
        .where(
            StoreProduct.size_category_id.in_(list(size_category_ids)),
            StoreProduct.store_id.in_(selected_store_ids(db, user)),
        )
        .order_by(StoreProduct.price, StoreProduct.id)
    )
    return [(product, store_name) for product, store_name in rows]


def product_out(product: StoreProduct, store_name: str) -> ProductOut:
    return ProductOut(
        id=product.id,
        store_id=product.store_id,
        store_name=store_name,
        name=product.name,
        brand=product.brand,
        price=product.price,
        image_url=product.image_url,
        updated_at=product.updated_at,
    )


def category_path(db: Session, category_id: int) -> str:
    names: list[str] = []
    next_id: int | None = category_id
    while next_id is not None:
        category = db.get_one(Category, next_id)
        names.insert(0, category.name)
        next_id = category.parent_id
    return " > ".join(names)


@router.get("/stores")
def get_stores(db: Db, user: CurrentUser) -> list[StoreOut]:
    selected = selected_store_ids(db, user)
    return [
        StoreOut(
            id=store.id,
            name=store.name,
            colour=store.colour,
            logo=store.logo,
            selected=store.id in selected,
        )
        for store in db.scalars(select(Store).order_by(Store.name))
    ]


@router.put("/me/stores", status_code=status.HTTP_204_NO_CONTENT)
def set_my_stores(selection: StoreSelection, db: Db, user: CurrentUser) -> None:
    wanted = set(selection.store_ids)
    known = set(db.scalars(select(Store.id).where(Store.id.in_(wanted))))
    if unknown := wanted - known:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown store: {min(unknown)}",
        )
    db.execute(delete(UserStore).where(UserStore.user_id == user.id))
    db.add_all(UserStore(user_id=user.id, store_id=store_id) for store_id in wanted)
    db.commit()


@router.get("/categories")
def get_categories(
    db: Db, _user: CurrentUser, parent_id: int | None = None
) -> list[CategoryOut]:
    rows = db.scalars(
        select(Category)
        .where(Category.parent_id == parent_id)
        .order_by(Category.size_amount, Category.name)
    )
    return [
        CategoryOut(id=row.id, parent_id=row.parent_id, name=row.name, level=row.level)
        for row in rows
    ]


@router.get("/categories/{category_id}/products")
def get_category_products(
    category_id: int, db: Db, user: CurrentUser, brand_q: str | None = None
) -> CategoryProducts:
    category = db.get(Category, category_id)
    if category is None or category.level != "size":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")

    rows = offers(db, user, [category_id])
    # The generic stays the true cheapest, so it's chosen before the brand filter.
    generic = product_out(*rows[0]) if rows else None
    # Carrefour has no brand field, so this looks at the whole name.
    wanted = fold((brand_q or "").strip())
    return CategoryProducts(
        generic=generic,
        products=[product_out(*row) for row in rows if wanted in row[0].search_text],
    )


@router.get("/search")
def search(q: str, db: Db, user: CurrentUser) -> list[SearchResult]:
    wanted = fold(q.strip())
    if not wanted:
        return []

    matches = db.scalars(
        select(StoreProduct).where(
            StoreProduct.store_id.in_(selected_store_ids(db, user)),
            StoreProduct.search_text.icontains(wanted, autoescape=True),
        )
    ).all()
    # A size with a name starting with the search outranks one that only mentions it.
    leads = {
        match.size_category_id for match in matches if match.search_text.startswith(wanted)
    }

    generics: dict[int, tuple[StoreProduct, str]] = {}
    for product, store_name in offers(db, user, {m.size_category_id for m in matches}):
        generics.setdefault(product.size_category_id, (product, store_name))

    ranked = sorted(
        generics,
        key=lambda size_id: (size_id not in leads, generics[size_id][0].price, size_id),
    )
    return [
        SearchResult(
            size_category_id=size_id,
            path=category_path(db, size_id),
            generic=product_out(*generics[size_id]),
        )
        for size_id in ranked[:MAX_SEARCH_RESULTS]
    ]
