"""Task 13: the Point Shop backend (wallet, rewards, redeem, vouchers), with the real database.

Points come from the points ledger: receipts add them, redeeming a reward
takes them off and gives a voucher. Each test is rolled back afterwards.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import create_token
from app.main import app
from app.models import PointsLedger, Reward, Store, User, Voucher


@pytest.fixture
def shopper(client: TestClient, db: Session) -> tuple[TestClient, User]:
    user = User(email="wallet-shopper@example.com", password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    return TestClient(app, headers={"Authorization": f"Bearer {create_token(user)}"}), user


def earn(db: Session, user: User, amount: int, reason: str = "Bon Auchan", when: datetime | None = None) -> None:
    entry = PointsLedger(user_id=user.id, amount=amount, reason=reason)
    if when:
        entry.created_at = when
    db.add(entry)
    db.flush()


@pytest.fixture
def rewards(db: Session) -> dict[str, Reward]:
    """Test rewards in their own store; the real loaded rewards may exist too."""
    store = Store(name="Magazin Point Shop Test", colour="#333333")
    db.add(store)
    db.flush()
    made = {
        "coffee": Reward(store_id=store.id, name="Cafea test", cost=500),
        "bread": Reward(store_id=store.id, name="Paine test", cost=300),
        "big": Reward(store_id=store.id, name="Reducere mare test", cost=5000),
        "retired": Reward(store_id=store.id, name="Retrasa test", cost=100, active=False),
    }
    db.add_all(made.values())
    db.flush()
    return made


def vouchers_of(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(Voucher).where(Voucher.user_id == user.id))


# --- Rewards ----------------------------------------------------------------


def test_active_rewards_are_listed_from_the_database(shopper, rewards) -> None:
    client, _ = shopper

    body = client.get("/api/rewards").json()

    mine = [r for r in body if r["store_name"] == "Magazin Point Shop Test"]
    assert sorted((r["name"], r["cost"]) for r in mine) == [("Cafea test", 500), ("Paine test", 300), ("Reducere mare test", 5000)]
    assert {r["id"] for r in mine} == {rewards[k].id for k in ("coffee", "bread", "big")}


def test_rewards_are_listed_cheapest_first(shopper, rewards) -> None:
    client, _ = shopper

    costs = [r["cost"] for r in client.get("/api/rewards").json()]

    assert costs == sorted(costs)


# --- Wallet -----------------------------------------------------------------


def test_balance_is_the_sum_of_the_ledger(db: Session, shopper) -> None:
    client, user = shopper
    earn(db, user, 260, "Bon Lidl", datetime(2026, 11, 1, tzinfo=UTC))
    earn(db, user, 1120, "Bon Auchan", datetime(2026, 11, 3, tzinfo=UTC))
    earn(db, user, -500, "Voucher: Cafea gratuită", datetime(2026, 11, 4, tzinfo=UTC))

    body = client.get("/api/wallet").json()

    assert body["balance"] == 880
    # Newest first.
    assert [(h["amount"], h["reason"]) for h in body["history"]] == [
        (-500, "Voucher: Cafea gratuită"),
        (1120, "Bon Auchan"),
        (260, "Bon Lidl"),
    ]
    assert body["history"][0]["created_at"].startswith("2026-11-04")


def test_empty_wallet(shopper) -> None:
    client, _ = shopper

    assert client.get("/api/wallet").json() == {"balance": 0, "history": []}


def test_wallet_shows_only_my_points(db: Session, shopper, other_client: TestClient) -> None:
    client, user = shopper
    earn(db, user, 100)

    assert other_client.get("/api/wallet").json()["balance"] == 0
    assert client.get("/api/wallet").json()["balance"] == 100


# --- Redeem -----------------------------------------------------------------


def test_redeeming_gives_a_voucher_and_takes_the_points(db: Session, shopper, rewards) -> None:
    client, user = shopper
    reward = rewards["coffee"]
    earn(db, user, reward.cost + 40)

    response = client.post(f"/api/rewards/{reward.id}/redeem")

    assert response.status_code == 201, response.text
    voucher = response.json()
    assert (voucher["reward_name"], voucher["store_name"]) == ("Cafea test", "Magazin Point Shop Test")
    assert voucher["code"].startswith("DD-") and len(voucher["code"]) == 11
    expires = datetime.fromisoformat(voucher["expires_at"])
    expected = datetime.now(UTC) + timedelta(days=get_settings().VOUCHER_VALID_DAYS)
    assert abs((expires - expected).total_seconds()) < 60

    wallet = client.get("/api/wallet").json()
    assert wallet["balance"] == 40
    assert (wallet["history"][0]["amount"], wallet["history"][0]["reason"]) == (-reward.cost, f"Voucher: {reward.name}")


def test_redeemed_voucher_is_listed(db: Session, shopper, rewards) -> None:
    client, user = shopper
    earn(db, user, 10_000)
    voucher = client.post(f"/api/rewards/{rewards['coffee'].id}/redeem").json()

    assert client.get("/api/vouchers").json() == [voucher]


def test_spending_exactly_the_balance_works_once(db: Session, shopper, rewards) -> None:
    client, user = shopper
    reward = {"id": rewards['bread'].id, "cost": rewards['bread'].cost}
    earn(db, user, reward["cost"])

    assert client.post(f"/api/rewards/{reward['id']}/redeem").status_code == 201
    second = client.post(f"/api/rewards/{reward['id']}/redeem")

    assert second.status_code == 409
    assert client.get("/api/wallet").json()["balance"] == 0
    assert vouchers_of(db, user) == 1


def test_too_few_points_is_refused_and_saves_nothing(db: Session, shopper, rewards) -> None:
    client, user = shopper
    reward = {"id": rewards['bread'].id, "cost": rewards['bread'].cost}
    earn(db, user, reward["cost"] - 1)

    response = client.post(f"/api/rewards/{reward['id']}/redeem")

    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)
    assert client.get("/api/wallet").json()["balance"] == reward["cost"] - 1
    assert vouchers_of(db, user) == 0


def test_unknown_reward(shopper) -> None:
    client, _ = shopper

    assert client.post("/api/rewards/999999999/redeem").status_code == 404


def test_hidden_reward_cannot_be_redeemed(db: Session, shopper, rewards) -> None:
    client, user = shopper
    earn(db, user, 10_000)

    assert client.post(f"/api/rewards/{rewards['retired'].id}/redeem").status_code == 404


def test_voucher_codes_are_unique(db: Session, shopper, rewards) -> None:
    client, user = shopper
    reward = {"id": rewards['bread'].id, "cost": rewards['bread'].cost}
    earn(db, user, reward["cost"] * 5)

    codes = {client.post(f"/api/rewards/{reward['id']}/redeem").json()["code"] for _ in range(5)}

    assert len(codes) == 5


# --- Vouchers ---------------------------------------------------------------


def test_used_expired_and_other_users_vouchers_are_hidden(db: Session, shopper, rewards, other_client: TestClient) -> None:
    client, user = shopper
    now = datetime.now(UTC)
    reward = rewards["coffee"]

    def voucher(code: str, **fields) -> Voucher:
        values = dict(
            user_id=user.id, reward_id=reward.id, reward_name=reward.name, store_name="Magazin Point Shop Test",
            code=code, expires_at=now + timedelta(days=5),
        )
        values.update(fields)
        return Voucher(**values)

    db.add_all([
        voucher("DD-VALID001"),
        voucher("DD-USED0001", used_at=now - timedelta(days=1)),
        voucher("DD-EXPIRED1", expires_at=now - timedelta(minutes=1)),
        voucher("DD-NEWER001", expires_at=now + timedelta(days=9)),
    ])
    db.flush()

    assert [v["code"] for v in client.get("/api/vouchers").json()] == ["DD-NEWER001", "DD-VALID001"]
    assert other_client.get("/api/vouchers").json() == []


# --- Login ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/wallet"), ("get", "/api/rewards"), ("get", "/api/vouchers"), ("post", "/api/rewards/1/redeem")],
)
def test_login_is_required(client: TestClient, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 401
