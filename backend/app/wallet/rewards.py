"""Point Shop rewards, from the database. Owner: Member 2, Task 13.

SAMPLE DATA: rewards come from data/rewards.yaml, loaded by
`uv run python -m dealdata.load`; spending points is simulated in the MVP.
Only active rewards are offered; ones taken out of the file stay in the
database, inactive, because redeemed vouchers point to them.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reward, Store


def active_rewards(db: Session) -> list[tuple[Reward, str]]:
    """Every active reward with its store's name, cheapest first."""
    rows = db.execute(
        select(Reward, Store.name)
        .join(Store, Store.id == Reward.store_id)
        .where(Reward.active.is_(True))
        .order_by(Reward.cost, Reward.id)
    ).all()
    return [(reward, store_name) for reward, store_name in rows]


def active_reward(db: Session, reward_id: int) -> tuple[Reward, str] | None:
    """One active reward with its store's name, or None."""
    row = db.execute(
        select(Reward, Store.name)
        .join(Store, Store.id == Reward.store_id)
        .where(Reward.id == reward_id, Reward.active.is_(True))
    ).first()
    return (row[0], row[1]) if row else None
