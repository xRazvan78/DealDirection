"""load_rewards(): Point Shop rewards from data/rewards.yaml into the database."""

from pathlib import Path

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reward, Store
from dealdata.load import load_rewards

REWARDS_FILE = Path(__file__).resolve().parents[2] / "data" / "rewards.yaml"


@pytest.fixture
def shops(db: Session) -> tuple[Store, Store]:
    made = (Store(name="Magazin Recompense A", colour="#111111"), Store(name="Magazin Recompense B", colour="#222222"))
    db.add_all(made)
    db.flush()
    return made


def saved(db: Session, store: Store) -> list[tuple[str, int, bool]]:
    rows = db.scalars(select(Reward).where(Reward.store_id == store.id).order_by(Reward.name))
    return [(r.name, r.cost, r.active) for r in rows]


def test_rewards_are_saved_under_their_store(db: Session, shops) -> None:
    a, b = shops

    load_rewards(db, [
        {"name": "Cafea test", "store": a.name, "cost": 500},
        {"name": "Paine test", "store": b.name, "cost": 300},
    ])

    assert saved(db, a) == [("Cafea test", 500, True)]
    assert saved(db, b) == [("Paine test", 300, True)]


def test_loading_again_updates_the_cost_and_keeps_the_id(db: Session, shops) -> None:
    a, _ = shops
    load_rewards(db, [{"name": "Cafea test", "store": a.name, "cost": 500}])
    first_id = db.scalar(select(Reward.id).where(Reward.store_id == a.id))

    load_rewards(db, [{"name": "Cafea test", "store": a.name, "cost": 450}])

    assert saved(db, a) == [("Cafea test", 450, True)]
    assert db.scalar(select(Reward.id).where(Reward.store_id == a.id)) == first_id


def test_a_reward_taken_out_of_the_file_is_hidden_not_deleted(db: Session, shops) -> None:
    a, _ = shops
    load_rewards(db, [{"name": "Cafea test", "store": a.name, "cost": 500}, {"name": "Ceai test", "store": a.name, "cost": 200}])

    load_rewards(db, [{"name": "Cafea test", "store": a.name, "cost": 500}])

    assert saved(db, a) == [("Cafea test", 500, True), ("Ceai test", 200, False)]


def test_a_reward_put_back_is_shown_again(db: Session, shops) -> None:
    a, _ = shops
    load_rewards(db, [{"name": "Ceai test", "store": a.name, "cost": 200}])
    load_rewards(db, [])

    load_rewards(db, [{"name": "Ceai test", "store": a.name, "cost": 250}])

    assert saved(db, a) == [("Ceai test", 250, True)]


def test_unknown_store_is_rejected(db: Session) -> None:
    with pytest.raises(ValueError, match="Nu Exista"):
        load_rewards(db, [{"name": "Cafea", "store": "Nu Exista", "cost": 500}])


@pytest.mark.parametrize("cost", [0, -5, "500"])
def test_cost_must_be_a_positive_whole_number(db: Session, shops, cost) -> None:
    with pytest.raises(ValueError):
        load_rewards(db, [{"name": "Cafea", "store": shops[0].name, "cost": cost}])


def test_real_rewards_file_is_valid() -> None:
    rewards = yaml.safe_load(REWARDS_FILE.read_text(encoding="utf-8"))["rewards"]
    stores = yaml.safe_load((REWARDS_FILE.parent / "stores.yaml").read_text(encoding="utf-8"))["stores"]

    assert rewards
    assert all(r["store"] in stores for r in rewards)
    assert all(isinstance(r["cost"], int) and r["cost"] > 0 for r in rewards)
    assert len({(r["store"], r["name"]) for r in rewards}) == len(rewards)
