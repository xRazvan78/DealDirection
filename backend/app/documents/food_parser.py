"""parse_foods(text) -> FoodList. Owner: Member 3, Task 10.

Reads lines like "200g piept de pui zilnic" from a shopping list or nutrition
plan. "zilnic" and "pe zi" mark a daily amount, and "<n> zile" sets the plan
length. Lines without an amount and unit are ignored.
"""

import re
from decimal import Decimal

from app.documents.schemas import Food, FoodList
from app.documents.text import fold

# Longer spellings first, so "grame" isn't read as "g" + "rame".
_UNITS = {
    "kilograme": "kg",
    "kilogram": "kg",
    "kg": "kg",
    "grame": "g",
    "gram": "g",
    "gr": "g",
    "g": "g",
    "mililitri": "ml",
    "ml": "ml",
    "litri": "l",
    "litru": "l",
    "l": "l",
    "bucati": "buc",
    "bucata": "buc",
    "buc": "buc",
}

_FOOD = re.compile(
    r"(?<![\d.,])(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>" + "|".join(_UNITS) + r")\.?(?=\s|$)"
    r"\s*(?:de\s+)?(?P<rest>.*)",
    re.IGNORECASE,
)
# A bare count is pieces: "2 oua zilnic". Day and meal numbers aren't foods.
_COUNT = re.compile(r"(?<![\d.,:])(?P<amount>\d+)\s+(?P<rest>[a-z].*)")
_NOT_FOODS = {"zi", "zile", "ziua", "zilei", "masa", "mese", "mesele", "ori", "saptamana", "saptamani", "luni", "x"}
_DAILY = re.compile(r"\b(?:zilnic|pe zi)\b", re.IGNORECASE)
_PLAN_DAYS = re.compile(r"\b(\d+)\s*zile\b")
_PLAN_PHRASE = re.compile(r"\b(?:timp de|pentru)?\s*\d+\s*zile\b", re.IGNORECASE)

# New lines and semicolons split items, and so does a comma not inside "1,5".
_SPLIT = re.compile(r"[\n;]|,(?!\d)")
_EDGE_PUNCTUATION = " \t.,;:-•*"


def parse_foods(text: str) -> FoodList:
    plan = _PLAN_DAYS.search(fold(text))
    foods = [food for part in _SPLIT.split(text) if (food := _parse_part(part))]
    return FoodList(plan_days=int(plan.group(1)) if plan else None, foods=foods)


def _parse_part(part: str) -> Food | None:
    # Fold only for finding the amount and unit; the name keeps its diacritics.
    folded = fold(part)
    match = _FOOD.search(folded)
    unit = _UNITS[match.group("unit").lower()] if match else "buc"
    if not match:
        match = _COUNT.search(folded)
        if not match or match.group("rest").split()[0].strip(_EDGE_PUNCTUATION) in _NOT_FOODS:
            return None

    original_rest = _original_tail(part, len(match.group("rest")))
    per_day = bool(_DAILY.search(original_rest))
    name = _DAILY.sub(" ", original_rest)
    name = _PLAN_PHRASE.sub(" ", name)
    name = " ".join(name.split()).strip(_EDGE_PUNCTUATION)
    if not name:
        return None

    return Food(
        name=name,
        amount=Decimal(match.group("amount").replace(",", ".")),
        unit=unit,
        per_day=per_day,
    )


def _original_tail(part: str, folded_length: int) -> str:
    """The last `folded_length` characters of `part`, with diacritics kept.

    fold() keeps one character per letter and collapses spaces, so we fold the
    original word by word and walk back until the lengths line up.
    """
    words = part.split()
    for start in range(len(words)):
        tail = " ".join(words[start:])
        if len(fold(tail)) <= folded_length:
            return tail
    return ""
