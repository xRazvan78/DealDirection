"""The Point Shop: points balance, history, rewards and vouchers. Owner: Member 2, Task 13.

Points live in points_ledger: receipts add them (Task 11), and redeeming a
reward (a partner gift card, see rewards.py) takes them off and creates a voucher. The balance is always the sum
of the ledger, so it can't drift from the history.

Redeeming locks the user's row first (SELECT ... FOR UPDATE), so two quick
taps run one after the other and can't spend the same points twice.
"""

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.models import PointsLedger, User, Voucher
from app.wallet.rewards import active_reward, active_rewards

router = APIRouter(tags=["wallet"])

# "DD-" and 8 letters and digits, without look-alikes such as 0/O and 1/I.
CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1I")
CODE_LENGTH = 8

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


class HistoryEntry(BaseModel):
    amount: int
    reason: str
    created_at: datetime


class WalletOut(BaseModel):
    balance: int
    history: list[HistoryEntry]


class RewardOut(BaseModel):
    id: int
    name: str
    cost: int
    store_name: str


class VoucherOut(BaseModel):
    id: int
    code: str
    reward_name: str
    store_name: str
    expires_at: datetime


@router.get("/wallet")
def get_wallet(user: CurrentUser, db: Db) -> WalletOut:
    entries = db.scalars(
        select(PointsLedger)
        .where(PointsLedger.user_id == user.id)
        .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
    ).all()
    return WalletOut(
        balance=sum(entry.amount for entry in entries),
        history=[
            HistoryEntry(amount=e.amount, reason=e.reason, created_at=e.created_at.astimezone(UTC)) for e in entries
        ],
    )


@router.get("/rewards")
def list_rewards(user: CurrentUser, db: Db) -> list[RewardOut]:
    """The partner gift cards on offer, from the database, cheapest first."""
    return [RewardOut(id=c.id, name=c.name, cost=c.cost_points, store_name=shop) for c, shop in active_rewards(db)]


@router.post("/rewards/{reward_id}/redeem", status_code=status.HTTP_201_CREATED)
def redeem_reward(reward_id: int, user: CurrentUser, db: Db) -> VoucherOut:
    found = active_reward(db, reward_id)
    if found is None:  # unknown, or taken out of the shop
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recompensa nu a fost găsită.")
    reward, store_name = found

    # Lock this user's row until commit: a second tap waits here, then sees the lower balance.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    balance = db.scalar(
        select(func.coalesce(func.sum(PointsLedger.amount), 0)).where(PointsLedger.user_id == user.id)
    )
    if balance < reward.cost_points:  # nothing was written; the lock ends with the request
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Nu ai destule puncte: ai {balance}, iar recompensa costă {reward.cost_points}.",
        )

    now = datetime.now(UTC)
    voucher = Voucher(
        user_id=user.id,
        gift_card_id=reward.id,
        reward_name=reward.name,
        store_name=store_name,
        code=_new_code(db),
        expires_at=now + timedelta(days=get_settings().VOUCHER_VALID_DAYS),
    )
    db.add(voucher)
    db.add(PointsLedger(user_id=user.id, amount=-reward.cost_points, reason=f"Voucher: {reward.name}"))
    try:
        db.flush()
        db.commit()
    except IntegrityError:  # a code taken at the same moment: vanishingly rare
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Încearcă din nou.") from None
    return _voucher_out(voucher)


@router.get("/vouchers")
def list_vouchers(user: CurrentUser, db: Db) -> list[VoucherOut]:
    """Vouchers that can still be used: not used and not expired, newest expiry first."""
    vouchers = db.scalars(
        select(Voucher)
        .where(Voucher.user_id == user.id, Voucher.used_at.is_(None), Voucher.expires_at > datetime.now(UTC))
        .order_by(Voucher.expires_at.desc(), Voucher.id.desc())
    )
    return [_voucher_out(v) for v in vouchers]


def _new_code(db: Session) -> str:
    while True:
        code = "DD-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if db.scalar(select(Voucher.id).where(Voucher.code == code)) is None:
            return code


def _voucher_out(voucher: Voucher) -> VoucherOut:
    return VoucherOut(
        id=voucher.id,
        code=voucher.code,
        reward_name=voucher.reward_name,
        store_name=voucher.store_name,
        expires_at=voucher.expires_at.astimezone(UTC),  # always UTC, whatever the database's zone
    )
