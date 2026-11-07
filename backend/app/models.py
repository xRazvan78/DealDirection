"""All SQLAlchemy models (README: Database tables). Owner: Member 2, Task 1.

Money and quantities are NUMERIC, never floats. Lists are soft deleted, so their
receipts and fingerprints stay in the database and a receipt can't be used twice.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

Money = Numeric(10, 2)
Quantity = Numeric(10, 3)


def utc_timestamp() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    colour: Mapped[str] = mapped_column(String(7))
    logo: Mapped[str | None] = mapped_column(String(500))


class StoreLocation(Base):
    __tablename__ = "store_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    address: Mapped[str] = mapped_column(String(300))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)


class UserStore(Base):
    """A store the user has selected."""

    __tablename__ = "user_stores"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("parent_id", "name"),
        CheckConstraint("level IN ('category', 'type', 'size')", name="level_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(10))
    size_amount: Mapped[Decimal | None] = mapped_column(Quantity)
    size_unit: Mapped[str | None] = mapped_column(String(10))
    aliases: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'"))


class StoreProduct(Base):
    __tablename__ = "store_products"
    __table_args__ = (UniqueConstraint("store_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    size_category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), index=True
    )
    type_category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(500))
    brand: Mapped[str | None] = mapped_column(String(200))
    barcode: Mapped[str | None] = mapped_column(String(50))
    price: Mapped[Decimal] = mapped_column(Money)
    unit: Mapped[str] = mapped_column(String(10))
    image_url: Mapped[str | None] = mapped_column(String(1000))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    search_text: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = utc_timestamp()


class ShoppingList(Base):
    """deleted_at set means the client deleted the list.

    It shows in the trash for TRASH_RETENTION_DAYS, then is hidden for good.
    Rows are never removed, and clearing deleted_at restores the list.
    """

    __tablename__ = "shopping_lists"
    __table_args__ = (
        CheckConstraint("state IN ('draft', 'active', 'completed')", name="state_valid"),
        Index("ix_shopping_lists_user_deleted", "user_id", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(10), server_default="draft")
    suggestion_shown: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    extra_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"))
    created_at: Mapped[datetime] = utc_timestamp()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ListItem(Base):
    __tablename__ = "list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id"), index=True)
    size_category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    chosen_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("store_products.id")
    )
    brand: Mapped[str | None] = mapped_column(String(200))
    quantity: Mapped[Decimal] = mapped_column(Quantity)
    assigned_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"))
    assigned_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("store_products.id")
    )
    estimated_price: Mapped[Decimal | None] = mapped_column(Money)
    removed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (UniqueConstraint("list_id", "store_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    # Not unique: two receipts can share a store, day and total. See receipts/router.py.
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    barcode: Mapped[str | None] = mapped_column(String(500), unique=True)
    unique_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    fiscal_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total: Mapped[Decimal] = mapped_column(Money)
    estimate: Mapped[Decimal] = mapped_column(Money)
    paid: Mapped[Decimal] = mapped_column(Money)
    modifier: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    points: Mapped[int] = mapped_column(Integer)


class ReceiptLine(Base):
    __tablename__ = "receipt_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    raw_text: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Quantity)
    line_total: Mapped[Decimal] = mapped_column(Money)
    matched_item_id: Mapped[int | None] = mapped_column(ForeignKey("list_items.id"))


class PointsLedger(Base):
    """The wallet balance is the sum of amount. receipt_id is empty for redemptions."""

    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id"))
    created_at: Mapped[datetime] = utc_timestamp()


class LoyaltyCard(Base):
    """A loyalty card: one per brand per user, for any supermarket in app.cards.brands.

    The code read from the card's photo is kept and redrawn cleanly at the till.
    The photo itself is only kept when no code could be read from it.
    """

    __tablename__ = "loyalty_cards"
    __table_args__ = (
        UniqueConstraint("user_id", "brand"),
        CheckConstraint("code_text IS NOT NULL OR photo IS NOT NULL", name="has_code_or_photo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand: Mapped[str] = mapped_column(String(30))
    code_text: Mapped[str | None] = mapped_column(String(500))
    code_format: Mapped[str | None] = mapped_column(String(20))
    photo: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = utc_timestamp()


class Reward(Base):
    """A Point Shop reward, loaded from data/rewards.yaml (SAMPLE DATA: spending is simulated).

    A reward taken out of the file is marked inactive, not deleted, because
    vouchers already redeemed point to it.
    """

    __tablename__ = "rewards"
    __table_args__ = (
        UniqueConstraint("store_id", "name"),
        CheckConstraint("cost > 0", name="cost_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    cost: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class PartnerShop(Base):
    """A coin shop partner where points are spent, filled by data/sql/*.sql (SAMPLE DATA).

    Same shape as data/sql/01_partner_shops_schema.sql: change both together.
    Switched off with active, never deleted, because vouchers will point to it.
    """

    __tablename__ = "partner_shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(300))
    website: Mapped[str | None] = mapped_column(String(300))
    colour: Mapped[str] = mapped_column(String(7))
    logo: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = utc_timestamp()


class PartnerGiftCard(Base):
    """A gift card a partner shop offers in the coin shop, worth value_lei for cost_points."""

    __tablename__ = "partner_gift_cards"
    __table_args__ = (
        UniqueConstraint("shop_id", "value_lei"),
        CheckConstraint("value_lei > 0", name="value_positive"),
        CheckConstraint("cost_points > 0", name="cost_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("partner_shops.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    value_lei: Mapped[Decimal] = mapped_column(Money)
    cost_points: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Voucher(Base):
    """A reward redeemed in the Point Shop. Its points were taken off in points_ledger.

    The reward's name and store are copied, so a voucher keeps what it was
    redeemed for even if the reward changes later. A voucher is shown until
    it's used or it expires.
    """

    __tablename__ = "vouchers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reward_id: Mapped[int] = mapped_column(ForeignKey("rewards.id"))
    reward_name: Mapped[str] = mapped_column(String(200))
    store_name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    created_at: Mapped[datetime] = utc_timestamp()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
