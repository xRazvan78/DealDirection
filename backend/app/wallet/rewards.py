"""Point Shop rewards, from the database. Owner: Member 2, Task 13.

The rewards on offer are the partner gift cards (Decathlon, Delfino, SuperBob),
in partner_gift_cards and filled by the SQL scripts in data/sql/
(`uv run python -m dealdata.run_sql`). SAMPLE DATA: spending points is simulated.
A card is offered only while both it and its shop are active. The old
supermarket rewards (rewards table) are no longer offered, but their vouchers stay.
"""

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import PartnerGiftCard, PartnerShop


def _offered() -> Select[tuple[PartnerGiftCard, str]]:
    return (
        select(PartnerGiftCard, PartnerShop.name)
        .join(PartnerShop, PartnerShop.id == PartnerGiftCard.shop_id)
        .where(PartnerGiftCard.active.is_(True), PartnerShop.active.is_(True))
    )


def active_rewards(db: Session) -> list[tuple[PartnerGiftCard, str]]:
    """Every gift card on offer with its shop's name, cheapest first."""
    rows = db.execute(
        _offered().order_by(PartnerGiftCard.cost_points, PartnerShop.name, PartnerGiftCard.id)
    ).all()
    return [(card, shop_name) for card, shop_name in rows]


def active_reward(db: Session, card_id: int) -> tuple[PartnerGiftCard, str] | None:
    """One gift card on offer with its shop's name, or None."""
    row = db.execute(_offered().where(PartnerGiftCard.id == card_id)).first()
    return (row[0], row[1]) if row else None
