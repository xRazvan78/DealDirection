"""parse_receipt(text) -> ReceiptData. Owner: Member 3, Task 10.

Shared patterns for Romanian fiscal receipts. An item is a name followed by a
line total ("PAINE ALBA   9,00 A"), optionally preceded by a quantity line
("2 BUC x 4,50" or "0,734 KG x 7,99"). Items stop at the TOTAL line.

Per-store rules get added here once real Auchan and Carrefour receipts are
saved as fixtures; until then only the shared layout is handled.
"""

import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.documents.schemas import ReceiptData, ReceiptLine
from app.documents.text import fold

STORES = {
    "auchan": "Auchan",
    "carrefour": "Carrefour",
    "lidl": "Lidl",
    "mega image": "Mega Image",
    "kaufland": "Kaufland",
    "profi": "Profi",
    "penny": "Penny",
}

_AMOUNT = r"\d+[.,]\d{2}"
# The unit is any short word, because OCR misreads "BUC" as "BUD" or "BUX", and
# the sign may be read as "x", "*" or a real "×". A trailing amount ("= 7,99" or
# just "7,99") is the line total. OCR can also split off the number, when the
# "Lei" column heading sits beside it: "1.000  Lei" then "BUC X 7.99".
_QUANTITY_LINE = re.compile(
    r"^(?:(?P<qty>\d+(?:[.,]\d+)?)\s*(?:[a-z]{1,4}\.?)?|buc\.?|kg\.?)\s*[x*×]\s*"
    rf"(?P<price>\d+[.,]\d{{2,3}})(?:\s*=?\s*(?P<total>{_AMOUNT}))?[\s.-]*[a-z]?$"
)
# The VAT letter may follow a space, dot or dash: "7,99 B", "7.99.B", "7,99-B".
# A discount's amount may also start with a minus: "-4,32".
_ITEM_LINE = re.compile(rf"^(?P<name>.*[a-z].*?)\s+-?(?P<total>{_AMOUNT})[\s.-]*[a-z]?$")
_TRAILING_AMOUNT = re.compile(rf"\s+-?{_AMOUNT}[\s.-]*[A-Za-z]?\s*$")
# A price OCR garbled beyond reading, like "6.993" (6.99 B) or "35:99t" (35,99 A).
_GARBLED_PRICE = re.compile(r"\s+\d+[.,:]\d{2}\S*\s*$")
# Up to a few stray characters between TOTAL and the amount: "TOTAL. 42.98", "TOTAL LEI: 42,98".
_TOTAL_LINE = re.compile(rf"^total\b(?!\s*tva)[^\d]{{0,8}}?(?P<total>{_AMOUNT})")
_NOT_ITEMS = ("subtotal", "total", "tva", "card", "numerar", "cash", "rest", "bon fiscal")
# Printed under the product it lowers. The amount has no reliable sign, because
# "7,99-B" is also how a plain price with its VAT letter can read.
_DISCOUNTS = ("discount", "reducere", "rabat", "promotie")
_CENT = Decimal("0.01")

# Only a possible time counts: a misread one must not cost us the date before it.
_TIME = r"(?:\s+(?:ora\W{0,2})?([01]\d|2[0-3])[:-]([0-5]\d)(?:[:-]([0-5]\d))?)?"
_DATE_DMY = re.compile(rf"(\d{{2}})[./-](\d{{2}})[./-](\d{{4}}){_TIME}")
_DATE_YMD = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[ t](\d{2}):(\d{2})(?::(\d{2}))?)?")

# A code printed to identify the receipt on its own: "ID BF: 8f31a2", "COD UNIC 1234".
_RECEIPT_ID = re.compile(r"\b(?:id\W{0,2}(?:bf|bon|unic)|cod\s+unic)\b\W{0,3}(?P<id>(?=[a-z-]*\d)[0-9a-z-]{4,})")
# A receipt number: "BF: 0025", "NR. BON 25", "BON FISCAL NR. 25".
_BON_NUMBER = re.compile(
    r"\b(?:bf|bon\s*(?:fiscal\s*)?(?:nr|numar)|(?:nr|numar)\W{0,2}bon(?:\s*fiscal)?)\b\W{0,3}(?P<number>\d+)\b"
)
_Z_NUMBER = re.compile(r"\bz\b\W{0,3}(?P<number>\d+)\b")


def parse_receipt(text: str) -> ReceiptData:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    folded = [fold(line) for line in raw_lines]
    return ReceiptData(
        store_name=_store_name(folded),
        purchased_at=_purchased_at(folded),
        total=_total(folded),
        lines=_items(raw_lines, folded),
        identifier=_identifier(folded),
    )


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", "."))


def _store_name(folded: list[str]) -> str:
    """The known store named earliest on the receipt, or "" if none is."""
    found = []
    for key, name in STORES.items():
        match = re.search(rf"\b{key}\b", "\n".join(folded))
        if match:
            found.append((match.start(), name))
    return min(found)[1] if found else ""


def _purchased_at(folded: list[str]) -> datetime | None:
    for line in folded:
        for pattern, order in ((_DATE_DMY, (2, 1, 0)), (_DATE_YMD, (0, 1, 2))):
            for match in pattern.finditer(line):
                parts = match.groups()
                year, month, day = (int(parts[i]) for i in order)
                hour, minute, second = (int(p) if p else 0 for p in parts[3:6])
                try:
                    return datetime(year, month, day, hour, minute, second)
                except ValueError:
                    continue  # e.g. 31.02.2026: keep looking
    return None


def _total(folded: list[str]) -> Decimal | None:
    for line in folded:
        match = _TOTAL_LINE.match(line)
        if match:
            return _decimal(match.group("total"))
    return None


def _identifier(folded: list[str]) -> str | None:
    """The printed receipt code, or None if OCR didn't read one.

    Receipt numbers restart at each daily Z report, so a plain number is only
    unique together with its Z number.
    """
    code = _first_match(_RECEIPT_ID, folded, "id")
    if code:
        return code.upper()
    number = _first_match(_BON_NUMBER, folded, "number")
    if number is None:
        return None
    z_number = _first_match(_Z_NUMBER, folded, "number")
    return f"Z {z_number} / BF {number}" if z_number else f"BF {number}"


def _first_match(pattern: re.Pattern[str], folded: list[str], group: str) -> str | None:
    return next((match.group(group) for match in map(pattern.search, folded) if match), None)


def _items(raw_lines: list[str], folded: list[str]) -> list[ReceiptLine]:
    items: list[ReceiptLine] = []
    pending_qty: Decimal | None = None
    pending_total: Decimal | None = None

    for raw, line in zip(raw_lines, folded):
        if _TOTAL_LINE.match(line):
            break

        quantity = _QUANTITY_LINE.match(line)
        if quantity:
            pending_qty = _decimal(quantity.group("qty") or "1")
            if quantity.group("total"):
                pending_total = _decimal(quantity.group("total"))
            else:
                # Used only if the name line's own price is unreadable.
                pending_total = (pending_qty * _decimal(quantity.group("price"))).quantize(_CENT, ROUND_HALF_UP)
            continue

        if line.startswith(_NOT_ITEMS):
            continue

        item = _ITEM_LINE.match(line)
        if item and line.startswith(_DISCOUNTS):
            if items:
                lowered = max(items[-1].line_total - _decimal(item.group("total")), Decimal(0))
                items[-1] = items[-1].model_copy(update={"line_total": lowered})
            continue

        if item:
            name = _TRAILING_AMOUNT.sub("", raw)
            total = _decimal(item.group("total"))
        elif pending_total is not None and re.search(r"[a-z]", line):
            # No readable price on the name line: take it from the quantity line.
            name, total = _GARBLED_PRICE.sub("", raw), pending_total
        else:
            continue

        items.append(ReceiptLine(raw_text=name, quantity=pending_qty or Decimal(1), line_total=total))
        pending_qty = pending_total = None

    return items
