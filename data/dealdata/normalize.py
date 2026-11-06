"""RawProduct, Size and parse_size(). Owner: Member 1, Task 4."""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class RawProduct:
    store: str
    name: str
    brand: str | None
    barcode: str | None
    price: Decimal
    image_url: str | None
    source_url: str


@dataclass(frozen=True)
class Size:
    amount: Decimal
    unit: str


# Each unit a store may print, with its factor and the app's unit (l, kg or buc).
_UNITS: dict[str, tuple[Decimal, str]] = {
    "l": (Decimal("1"), "l"),
    "litru": (Decimal("1"), "l"),
    "litri": (Decimal("1"), "l"),
    "dl": (Decimal("0.1"), "l"),
    "cl": (Decimal("0.01"), "l"),
    "ml": (Decimal("0.001"), "l"),
    "kg": (Decimal("1"), "kg"),
    "g": (Decimal("0.001"), "kg"),
    "gr": (Decimal("0.001"), "kg"),
    "grame": (Decimal("0.001"), "kg"),
    "buc": (Decimal("1"), "buc"),
    "bucata": (Decimal("1"), "buc"),
    "bucată": (Decimal("1"), "buc"),
    "bucati": (Decimal("1"), "buc"),
    "bucăți": (Decimal("1"), "buc"),
    "rola": (Decimal("1"), "buc"),
    "role": (Decimal("1"), "buc"),
    "plic": (Decimal("1"), "buc"),
    "plicuri": (Decimal("1"), "buc"),
    "pliculete": (Decimal("1"), "buc"),
    "capsula": (Decimal("1"), "buc"),
    "capsule": (Decimal("1"), "buc"),
    "spalari": (Decimal("1"), "buc"),
    "spălări": (Decimal("1"), "buc"),
}

# The lookarounds stop "5" in "0.5" or "1,5" starting a match, and "l" in "4 lapte"
# being a unit. A comma after a word is fine, as in "Classica ,250G".
_SIZE = re.compile(
    r"(?<![\w.])(?<!\d,)"
    r"(?:(?P<count>\d+)\s*[x×*]\s*)?"
    r"(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?:de\s+)?"
    rf"(?P<unit>{'|'.join(_UNITS)})"
    r"(?!\w)"
)


def parse_size(name: str) -> Size | None:
    """Return the first size in a product name, converted to l, kg or buc."""
    match = _SIZE.search(name.lower())
    if match is None:
        return None

    factor, unit = _UNITS[match["unit"]]
    amount = Decimal(match["amount"].replace(",", ".")) * factor
    if match["count"]:
        amount *= int(match["count"])
    # The database keeps 3 decimals, so sizes must match it exactly.
    return Size(amount.quantize(Decimal("0.001"), ROUND_HALF_UP), unit)
