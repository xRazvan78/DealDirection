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
# A trailing amount ("= 7,99" or just "7,99") is the line total. OCR can also
# split off the number, when the "Lei" heading sits beside it: "1.000  Lei" then "BUC X 7.99".
_QUANTITY_LINE = re.compile(
    r"^(?:(?P<qty>\d+(?:[.,]\d+)?)\s*(?:[a-z]{1,4}\.?)?|buc\.?|kg\.?)\s*[x×*]\s*"
    rf"(?P<price>\d+[.,]\d{{2,3}})(?:\s*=?\s*(?P<total>{_AMOUNT}))?{_VAT}$"
)
# A discount's amount may start with a minus: "-4,32".
_ITEM_LINE = re.compile(rf"^(?P<name>.*[a-z].*?)\s+-?(?P<total>{_AMOUNT}){_VAT}$")
# A minus after the amount ("4,32-C") or a discount word marks a discount.
_DISCOUNT_LINE = re.compile(rf"^(?P<name>.*[a-z].*?)\s+-?(?P<amount>{_AMOUNT})\s*-[\s.]*[a-z]?$")
_DISCOUNT_WORDS = ("discount", "reducere", "rabat", "promotie")
_DEPOSIT_WORDS = ("ambalaj", "sgr", "garantie")
_TRAILING_AMOUNT = re.compile(rf"\s+-?{_AMOUNT}[\s.\-]*[A-Za-z]?\s*$")
# A price that OCR put on its own line, with at most its VAT letter: "7.99 B", "B 7,99".
_PRICE_ALONE = re.compile(rf"^\W*[a-z]?\W*(?P<total>{_AMOUNT}){_VAT}\W*$")
# A product's name has a real word in it, which a VAT letter or stray mark doesn't.
_NAME_WORD = re.compile(r"[a-z]{3,}")
# A price OCR garbled beyond reading, like "6.993" (6.99 B) or "35:99t" (35,99 A).
_GARBLED_PRICE = re.compile(r"\s+\d+[.,:]\d{2}\S*\s*$")
# Up to a few stray characters between TOTAL and the amount: "TOTAL. 42.98", "TOTAL LEI: 42,98".
_TOTAL_LINE = re.compile(rf"^total\b(?!\s*tva)[^\d]{{0,8}}?(?P<total>{_AMOUNT})")
_NOT_ITEMS = ("subtotal", "total", "tva", "card", "numerar", "cash", "rest", "bon fiscal")
_CENT = Decimal("0.01")

# Only a possible time counts: a misread one must not cost us the date before it.
_TIME = r"(?:\s+(?:ora\W{0,2})?([01]\d|2[0-3])[:-]([0-5]\d)(?:[:-]([0-5]\d))?)?"
_DATE_DMY = re.compile(rf"(\d{{2}})[./-](\d{{2}})[./-](\d{{4}}){_TIME}")
_DATE_YMD = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[ t](\d{2}):(\d{2})(?::(\d{2}))?)?")
# "ORA:21-36-05". A seconds part cut short ("21-37-3") is left out.
_ORA = re.compile(r"\bora\b\s*:?\s*(\d{1,2})[-:.](\d{2})(?:[-:.](\d{2})(?!\d))?")
_ID_UNIC = re.compile(r"\bid\s*unic\b\s*:?\s*((?:\d ?){10,40})")
_REGISTER = re.compile(r"\brl\b\s*:?\s*(\d{6,12})\b")
_RECEIPT_NUMBER = re.compile(r"\bbf\b\.?\s*:?\s*(\d{1,6})\b")

# A code printed to identify the receipt on its own: "ID BF: 8f31a2", "COD UNIC 1234".
_RECEIPT_ID = re.compile(r"\b(?:id\W{0,2}(?:bf|bon|unic)|cod\s+unic)\b\W{0,3}(?P<id>(?=[a-z-]*\d)[0-9a-z-]{4,})")
UNIQUE_ID_LENGTH = 32
# A receipt number: "BF: 0025", "NR. BON 25", "BON FISCAL NR. 25".
_BON_NUMBER = re.compile(
    r"\b(?:bf|bon\s*(?:fiscal\s*)?(?:nr|numar)|(?:nr|numar)\W{0,2}bon(?:\s*fiscal)?)\b\W{0,3}(?P<number>\d+)\b"
)
_Z_NUMBER = re.compile(r"\bz\b\W{0,3}(?P<number>\d+)\b")


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
        identifier=_identifier(folded),
        unique_id=_unique_id(fiscal),
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
            pending_qty = _decimal(quantity.group("qty") or "1")
            if quantity.group("total"):
                pending_total = _decimal(quantity.group("total"))
            else:
                # Used only if the name line's own price is unreadable.
                pending_total = (pending_qty * _decimal(quantity.group("price"))).quantize(_CENT, ROUND_HALF_UP)
            continue

        if line.startswith(_NOT_ITEMS) or line == "lei":
            continue

        price = _PRICE_ALONE.match(line)
        if price:
            # Its name is on another line. The printed price beats a computed one.
            if pending_qty is not None:
                pending_total = _decimal(price.group("total"))
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
        elif pending_total is not None:
            # No readable price on the name line: take it from the quantity line.
            name, total = _GARBLED_PRICE.sub("", raw), pending_total
        else:
            continue

        if not _NAME_WORD.search(fold(name)):
            continue  # stray OCR marks; the real name may still be on the next line

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


def _unique_id(fiscal: _Fiscal) -> str | None:
    """The ID UNIC, only if it's whole and agrees with the rest of the receipt.

    Duplicate checks rely on it, and a misread would let a receipt through twice.
    """
    code = fiscal.receipt_id
    if code is None or len(code) != UNIQUE_ID_LENGTH:
        return None
    if fiscal.purchased_at and code[10:18] != fiscal.purchased_at.strftime("%Y%m%d"):
        return None
    if fiscal.receipt_number and int(code[-4:]) != int(fiscal.receipt_number[-4:]):
        return None
    return code


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
