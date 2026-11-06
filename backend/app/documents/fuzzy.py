"""score_line(): rapidfuzz matching of receipt lines to items. Owner: Member 3, Task 10.

A receipt line is matched to a list item by
    0.7 x name similarity (token_set_ratio) + 0.3 x price closeness.
Both parts are 0-100, so the score is 0-100. A brand item also needs its brand
on the line. The weights and minimum score are starting values, tuned later on
real receipts.
"""

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal

from rapidfuzz import fuzz

from app.documents.schemas import Food, FoodMapping, LineMatch, ReceiptLine
from app.documents.text import fold

NAME_WEIGHT = 0.7
PRICE_WEIGHT = 0.3
BRAND_MIN_PARTIAL = 80


def normalize(text: str, abbreviations: Mapping[str, str] | None = None) -> str:
    """Fold, use "." in decimals, split "1L" into "1 l", and expand abbreviations."""
    text = fold(text)
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = re.sub(r"(?<=\d)(?=[a-z])", " ", text)
    for short, full in sorted((abbreviations or {}).items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"\b{re.escape(fold(short))}\b", fold(full), text)
    return " ".join(text.split())


def price_closeness(line: ReceiptLine, expected_price: Decimal) -> float:
    """100 when the line's unit price equals the expected price, down to 0."""
    if line.quantity <= 0 or expected_price <= 0:
        return 0.0
    unit_price = line.line_total / line.quantity
    gap = abs(unit_price - expected_price) / expected_price
    return float(100 * max(Decimal(0), 1 - gap))


def score_line(line: ReceiptLine, item: Mapping, abbreviations: Mapping[str, str]) -> float:
    """Score one receipt line against one item dict (id, name, brand, expected_price)."""
    text = normalize(line.raw_text, abbreviations)

    brand = item.get("brand")
    if brand and fuzz.partial_ratio(fold(brand), text) < BRAND_MIN_PARTIAL:
        return 0.0

    name_score = fuzz.token_set_ratio(text, normalize(item["name"]))
    price_score = price_closeness(line, Decimal(item["expected_price"]))
    return NAME_WEIGHT * name_score + PRICE_WEIGHT * price_score


def match_lines(
    lines: Sequence[ReceiptLine],
    items: Sequence[Mapping],
    abbreviations: Mapping[str, str],
    min_score: float,
) -> list[LineMatch]:
    """Pair lines with items, best scores first, each line and item used once."""
    scored = [
        (score_line(line, item, abbreviations), index, item["id"])
        for index, line in enumerate(lines)
        for item in items
    ]
    # Highest score first; ties go to the earlier line, then the lower item id.
    scored.sort(key=lambda s: (-s[0], s[1], s[2]))

    used_lines: set[int] = set()
    used_items: set[int] = set()
    matches: list[LineMatch] = []
    for score, index, item_id in scored:
        if score < min_score:
            break
        if index in used_lines or item_id in used_items:
            continue
        used_lines.add(index)
        used_items.add(item_id)
        matches.append(LineMatch(line_index=index, item_id=item_id))
    return matches


def map_foods(foods: Sequence[Food], leaves: Sequence[Mapping], min_score: float) -> list[FoodMapping]:
    """Map each food to a size-level category by its aliases and type names.

    `leaves` dicts hold id, path (category, type, size) and aliases. A food
    with no candidate at or above `min_score` gets no category. On a tie the
    leaf given first wins, so callers should list the most common ones first.
    """
    candidates: list[tuple[int, str]] = []
    for leaf in leaves:
        names = list(leaf.get("aliases") or [])
        path = leaf.get("path") or []
        names += list(path[:2]) + [" ".join(path[:2])]
        candidates += [(leaf["id"], normalize(name)) for name in names if name]

    mappings = []
    for food in foods:
        wanted = normalize(food.name)
        best_id, best_score = None, 0.0
        for leaf_id, name in candidates:
            score = fuzz.token_sort_ratio(wanted, name)
            if score > best_score:  # ties keep the earlier leaf: callers list common ones first
                best_id, best_score = leaf_id, score
        mappings.append(
            FoodMapping(
                food_name=food.name,
                size_category_id=best_id if best_score >= min_score else None,
            )
        )
    return mappings
