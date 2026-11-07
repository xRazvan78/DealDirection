"""parse_receipt(text) -> ReceiptData. Owner: Member 3, Task 10.

Romanian fiscal receipts print each product as an optional quantity line, then
the product name with the line total and its VAT letter:

    2.000  BUC X 4.79
    CHIO HULA HOOPS70G          9.58 C

Products stop at the TOTAL line. Along the way:
- a discount ("DISCOUNT 4,32-C") is taken off the product above it;
- bottle deposits ("GARANTIE AMBALAJ", SGR) are paid but aren't products, so
  they're counted apart;
- `adds_up` checks products + deposits against the printed TOTAL, so a misread
  receipt can be caught instead of earning wrong points.

The fiscal identifiers are read too. The 32-digit ID UNIC is the register
series (also printed after "RL"), the date, the time, 4 more digits and the
receipt number (also printed after "BF"). Long digit runs are easy for OCR to
misread, so `fiscal_key` is built from register, date, time and number, each
taken from its own printed field or from the ID UNIC when that lines up with
the date.

Tested on real Lidl and Kaufland receipts (tests/fixtures/receipts/).
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time
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
# After a price: the VAT letter, after a space, dash or dot, or none ("7,99 B", "7,99-B", "7,99.B", "7,99B").
_VAT = r"[\s.\-]*[a-z]?"
# The unit is any short word, because OCR misreads "BUC" as "BUD" or "BUX".
# The sign is x, X, * or the "×" that OCR often reads instead.
# A trailing amount ("= 7,99" or just "7,99") is the line total.
_QUANTITY_LINE = re.compile(
    r"^(?P<qty>\d+(?:[.,]\d+)?)\s*(?:[a-z]{1,4}\.?)?\s*[x×*]\s*"
    rf"(?P<price>\d+[.,]\d{{2,3}})(?:\s*=?\s*(?P<total>{_AMOUNT}))?{_VAT}$"
)
_ITEM_LINE = re.compile(rf"^(?P<name>.*[a-z].*?)\s+(?P<total>{_AMOUNT}){_VAT}$")
# A minus after the amount ("4,32-C") or a discount word marks a discount.
_DISCOUNT_LINE = re.compile(rf"^(?P<name>.*[a-z].*?)\s+-?(?P<amount>{_AMOUNT})\s*-[\s.]*[a-z]?$")
_DISCOUNT_WORDS = ("discount", "reducere")
_DEPOSIT_WORDS = ("ambalaj", "sgr", "garantie")
_TRAILING_AMOUNT = re.compile(rf"\s+{_AMOUNT}[\s.\-]*[A-Za-z]?\s*$")
# A price OCR garbled beyond reading, like "6.993" (6.99 B) or "35:99t" (35,99 A).
_GARBLED_PRICE = re.compile(r"\s+\d+[.,:]\d{2}\S*\s*$")
# Up to a few stray characters between TOTAL and the amount: "TOTAL. 42.98", "TOTAL LEI: 42,98".
_TOTAL_LINE = re.compile(rf"^total\b(?!\s*tva)[^\d]{{0,8}}?(?P<total>{_AMOUNT})")
_NOT_ITEMS = ("subtotal", "total", "tva", "card", "numerar", "cash", "rest", "bon fiscal")
_CENT = Decimal("0.01")

_DATE_DMY = re.compile(r"(\d{2})[./-](\d{2})[./-](\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?")
_DATE_YMD = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[ t](\d{2}):(\d{2})(?::(\d{2}))?)?")
# "ORA:21-36-05". A seconds part cut short ("21-37-3") is left out.
_ORA = re.compile(r"\bora\b\s*:?\s*(\d{1,2})[-:.](\d{2})(?:[-:.](\d{2})(?!\d))?")
_ID_UNIC = re.compile(r"\bid\s*unic\b\s*:?\s*((?:\d ?){10,40})")
_REGISTER = re.compile(r"\brl\b\s*:?\s*(\d{6,12})\b")
_RECEIPT_NUMBER = re.compile(r"\bbf\b\.?\s*:?\s*(\d{1,6})\b")


def parse_receipt(text: str) -> ReceiptData:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    folded = [fold(line) for line in raw_lines]
    lines, deposits = _items(raw_lines, folded)
    total = _total(folded)
    fiscal = _fiscal(folded)
    adds_up = None if total is None else abs(sum((l.line_total for l in lines), deposits) - total) <= _CENT
    return ReceiptData(
        store_name=_store_name(folded),
        purchased_at=fiscal.purchased_at,
        total=total,
        lines=lines,
        deposits=deposits,
        adds_up=adds_up,
        receipt_id=fiscal.receipt_id,
        register_id=fiscal.register_id,
        receipt_number=fiscal.receipt_number,
        fiscal_key=fiscal.key,
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


def _total(folded: list[str]) -> Decimal | None:
    for line in folded:
        match = _TOTAL_LINE.match(line)
        if match:
            return _decimal(match.group("total"))
    return None


def _items(raw_lines: list[str], folded: list[str]) -> tuple[list[ReceiptLine], Decimal]:
    """The products, with discounts taken off, and the total of bottle deposits."""
    items: list[ReceiptLine] = []
    deposits = Decimal(0)
    pending_qty: Decimal | None = None
    pending_total: Decimal | None = None

    for raw, line in zip(raw_lines, folded):
        if _TOTAL_LINE.match(line):
            break

        quantity = _QUANTITY_LINE.match(line)
        if quantity:
            pending_qty = _decimal(quantity.group("qty"))
            if quantity.group("total"):
                pending_total = _decimal(quantity.group("total"))
            else:
                # Used only if the name line's own price is unreadable.
                pending_total = (pending_qty * _decimal(quantity.group("price"))).quantize(_CENT, ROUND_HALF_UP)
            continue

        if line.startswith(_NOT_ITEMS):
            continue

        # A minus before the VAT letter can also be OCR misreading a space
        # ("7,99-B"). A product follows its quantity line; a discount never does.
        named_discount = line.startswith(_DISCOUNT_WORDS)
        discount = _DISCOUNT_LINE.match(line) if pending_qty is None or named_discount else None
        item = _ITEM_LINE.match(line)
        if discount or (item and named_discount):
            amount = _decimal(discount.group("amount") if discount else item.group("total"))
            if items:  # a discount belongs to the product above it
                last = items[-1]
                items[-1] = last.model_copy(update={"line_total": max(Decimal("0.00"), last.line_total - amount)})
            pending_qty = pending_total = None
            continue

        if item:
            name = _TRAILING_AMOUNT.sub("", raw)
            total = _decimal(item.group("total"))
        elif pending_total is not None and re.search(r"[a-z]", line):
            # No readable price on the name line: take it from the quantity line.
            name, total = _GARBLED_PRICE.sub("", raw), pending_total
        else:
            continue

        if any(word in line for word in _DEPOSIT_WORDS):
            deposits += total  # a bottle deposit: paid, but not a product
        else:
            items.append(ReceiptLine(raw_text=name, quantity=pending_qty or Decimal(1), line_total=total))
        pending_qty = pending_total = None

    return items, deposits


@dataclass(frozen=True)
class _Fiscal:
    purchased_at: datetime | None
    receipt_id: str | None
    register_id: str | None
    receipt_number: str | None
    key: str | None


def _fiscal(folded: list[str]) -> _Fiscal:
    """The purchase time and the receipt's fiscal identifiers."""
    text = "\n".join(folded)
    day, inline_time = _date(folded)

    receipt_id = None
    if match := _ID_UNIC.search(text):
        receipt_id = re.sub(r"\D", "", match.group(1))

    # Trust the ID UNIC's parts only when its date sits where it should.
    id_register = id_time = id_number = None
    if receipt_id and day and receipt_id[10:18] == day.strftime("%Y%m%d"):
        id_register = receipt_id[:10]
        id_time = _hhmmss(receipt_id[18:24]) if len(receipt_id) >= 24 else None
        id_number = str(int(receipt_id[28:32])) if len(receipt_id) == 32 else None

    ora_time = None
    if match := _ORA.search(text):
        hour, minute, second = match.groups()
        ora_time = _time(int(hour), int(minute), int(second or 0))

    register = (m.group(1) if (m := _REGISTER.search(text)) else None) or id_register
    number = (str(int(m.group(1))) if (m := _RECEIPT_NUMBER.search(text)) else None) or id_number
    clock = inline_time or ora_time or id_time

    purchased_at = datetime.combine(day, clock or time()) if day else None
    key = None
    if register and day and clock and number:
        key = f"{register}|{day:%Y%m%d}|{clock:%H%M}|{number}"
    return _Fiscal(purchased_at, receipt_id, register, number, key)


def _date(folded: list[str]) -> tuple[date | None, time | None]:
    """The first valid date, and a time printed right after it, if any."""
    for line in folded:
        for pattern, order in ((_DATE_DMY, (2, 1, 0)), (_DATE_YMD, (0, 1, 2))):
            for match in pattern.finditer(line):
                parts = match.groups()
                year, month, day = (int(parts[i]) for i in order)
                try:
                    found = date(year, month, day)
                except ValueError:
                    continue  # e.g. 31.02.2026: keep looking
                clock = _time(int(parts[3]), int(parts[4]), int(parts[5] or 0)) if parts[3] else None
                return found, clock
    return None, None


def _hhmmss(digits: str) -> time | None:
    return _time(int(digits[0:2]), int(digits[2:4]), int(digits[4:6])) if len(digits) == 6 else None


def _time(hour: int, minute: int, second: int) -> time | None:
    try:
        return time(hour, minute, second)
    except ValueError:
        return None
