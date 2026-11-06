"""fingerprint() and score_matches(). Owner: Member 3, Task 11.

Pure logic: no database or HTTP, so the receipt rules are testable alone.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.documents.schemas import LineMatch, ReceiptLine
from app.textutil import fold

CENT = Decimal("0.01")


@dataclass(frozen=True)
class MatchedLine:
    line_index: int
    item_id: int
    quantity: Decimal  # what counts: the smaller of the list and receipt quantities
    estimate: Decimal  # the app's price for that quantity
    paid: Decimal  # the receipt's price for that quantity


def fingerprint(store_id: int, purchased_at: datetime, total: Decimal) -> str:
    """Identify a paper receipt, so it can only earn points once.

    Uses the store, the purchase date and the total. The time of day is left
    out on purpose: OCR reads it on one scan and misses it on the next, and a
    rescan of the same paper must still count as the same receipt.
    """
    key = f"{store_id}|{purchased_at.date().isoformat()}|{total.quantize(CENT)}"
    return hashlib.sha256(key.encode()).hexdigest()


def merge_repeated_lines(lines: Sequence[ReceiptLine]) -> list[ReceiptLine]:
    """Combine lines for the same product into one, in first-seen order.

    Items scanned one by one at the till print as separate, identical lines.
    Each line matches at most one list item, so two bags of chips on a list
    need the two chips lines combined into one line of quantity 2.
    """
    merged: dict[str, ReceiptLine] = {}
    for line in lines:
        key = " ".join(fold(line.raw_text).split())  # OCR spacing varies between lines
        seen = merged.get(key)
        merged[key] = (
            line
            if seen is None
            else ReceiptLine(
                raw_text=seen.raw_text,
                quantity=seen.quantity + line.quantity,
                line_total=seen.line_total + line.line_total,
            )
        )
    return list(merged.values())


def score_matches(
    matches: Sequence[LineMatch],
    lines: Sequence[ReceiptLine],
    items: Sequence[Mapping],
) -> tuple[Decimal, Decimal, list[MatchedLine]]:
    """Total the matched lines into (estimate, paid, matched lines).

    `items` dicts hold id, quantity and estimated_price (per unit). For each
    match, only up to the listed quantity counts: buying 5 packs of a 1-pack
    item earns points for 1, and 0.734 kg of a 1 kg item earns for 0.734 kg.
    Matches to unknown items or lines, and repeats, are ignored.
    """
    by_id = {item["id"]: item for item in items}
    used_lines: set[int] = set()
    used_items: set[int] = set()
    matched: list[MatchedLine] = []

    for match in matches:
        item = by_id.get(match.item_id)
        if item is None or not 0 <= match.line_index < len(lines):
            continue
        if match.line_index in used_lines or match.item_id in used_items:
            continue
        line = lines[match.line_index]
        if line.quantity <= 0:
            continue

        quantity = min(Decimal(item["quantity"]), line.quantity)
        estimate = (Decimal(item["estimated_price"]) * quantity).quantize(CENT, ROUND_HALF_UP)
        paid = (line.line_total / line.quantity * quantity).quantize(CENT, ROUND_HALF_UP)
        used_lines.add(match.line_index)
        used_items.add(match.item_id)
        matched.append(MatchedLine(match.line_index, match.item_id, quantity, estimate, paid))

    estimate_total = sum((m.estimate for m in matched), Decimal(0))
    paid_total = sum((m.paid for m in matched), Decimal(0))
    return estimate_total, paid_total, matched
