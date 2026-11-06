"""scale_foods(), packs_needed() and choose_size(). Owner: Member 3, Task 12.

Pure logic: turns the foods read from a list or nutrition plan into amounts
to buy, and amounts into whole packs of a real size.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.documents.schemas import FoodList
from app.textutil import fold

# Grams and millilitres are stored as kilograms and litres, like category sizes.
_TO_BASE = {"g": ("kg", Decimal("0.001")), "ml": ("l", Decimal("0.001"))}

# choose_size(): each pack beyond the first costs as much as wasting 15% of the amount.
EXTRA_PACK_COST = Decimal("0.15")


@dataclass(frozen=True)
class ScaledFood:
    name: str
    amount: Decimal
    unit: str  # kg, l or buc


@dataclass(frozen=True)
class Size:
    id: int
    amount: Decimal
    unit: str  # kg, l or buc, as stored on size-level categories


def to_base(amount: Decimal, unit: str) -> tuple[Decimal, str]:
    """Convert g to kg and ml to l; other units stay as they are."""
    base_unit, factor = _TO_BASE.get(unit, (unit, Decimal(1)))
    return amount * factor, base_unit


def scale_foods(food_list: FoodList, days: int) -> list[ScaledFood]:
    """Amounts to buy for `days` days, in kg, l or buc.

    Daily foods ("zilnic", "pe zi") are multiplied by `days`. Other foods are
    for the whole plan, so they're multiplied by days / plan_days when the
    plan length is known, and kept as written when it isn't. Repeated foods
    in the same unit are added up, under their first spelling.
    """
    totals: dict[tuple[str, str], ScaledFood] = {}
    for food in food_list.foods:
        amount, unit = to_base(food.amount, food.unit)
        if food.per_day:
            amount *= days
        elif food_list.plan_days:
            amount = amount * days / food_list.plan_days

        key = (" ".join(fold(food.name).split()), unit)
        seen = totals.get(key)
        totals[key] = ScaledFood(seen.name if seen else food.name.strip(), (seen.amount if seen else 0) + amount, unit)
    return list(totals.values())


def packs_needed(amount: Decimal, unit: str, leaf_amount: Decimal, leaf_unit: str) -> int | None:
    """Whole packs of `leaf_amount` needed for `amount`, or None if the units differ."""
    amount, unit = to_base(Decimal(amount), unit)
    leaf_amount, leaf_unit = to_base(Decimal(leaf_amount), leaf_unit)
    if unit != leaf_unit or leaf_amount <= 0:
        return None
    return max(1, math.ceil(amount / leaf_amount))


def choose_size(amount: Decimal, unit: str, sizes: Sequence[Size]) -> tuple[int, int] | None:
    """The best (size id, packs) for `amount`, or None if no size has its unit.

    Balances waste against the number of packs: wasting nothing with 14 x
    100 g is worse than 3 x 500 g for 1.4 kg, and one 10 kg sack is worse
    than one 500 g pack for 400 g. Ties go to the first size given.
    """
    amount, unit = to_base(Decimal(amount), unit)
    if amount <= 0:
        return None

    best: tuple[Decimal, int, int] | None = None
    for size in sizes:
        packs = packs_needed(amount, unit, size.amount, size.unit)
        if packs is None:
            continue
        waste = packs * to_base(size.amount, size.unit)[0] - amount
        cost = waste / amount + EXTRA_PACK_COST * (packs - 1)
        if best is None or cost < best[0]:
            best = (cost, size.id, packs)
    return (best[1], best[2]) if best else None
