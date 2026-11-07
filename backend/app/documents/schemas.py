"""ReceiptData, FoodList, LineMatch and FoodMapping models. Owner: Member 3, Task 10.

These are the only shapes that leave the documents unit, so the receipt and
import routes (Tasks 11 and 12) never see OCR text or engine details.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class DocumentError(Exception):
    """The file couldn't be read: bad bytes, a timeout, or an OCR failure."""


class ReceiptLine(_Frozen):
    raw_text: str
    quantity: Decimal
    line_total: Decimal


class ReceiptData(_Frozen):
    store_name: str
    purchased_at: datetime | None
    total: Decimal | None
    lines: list[ReceiptLine]  # products only: discounts are taken off, deposits left out
    deposits: Decimal = Decimal(0)  # bottle deposits (SGR): paid, but not products
    adds_up: bool | None = None  # products + deposits == total; None without a total
    receipt_id: str | None = None  # the ID UNIC digits, as read
    register_id: str | None = None  # the cash register's series, printed after "RL"
    receipt_number: str | None = None  # "BF" number, without leading zeros
    # register|date|HHMM|number: identifies one paper receipt even if the ID UNIC is misread
    fiscal_key: str | None = None
    identifier: str | None = None  # the best printed number OCR read, checked or not
    barcode: str | None = None  # the decoded barcode or QR code
    unique_id: str | None = None  # the ID UNIC, only if it passed its checks


class Food(_Frozen):
    name: str
    amount: Decimal
    unit: str  # g, kg, ml, l or buc, as written; Task 12 converts g/ml
    per_day: bool


class FoodList(_Frozen):
    plan_days: int | None
    foods: list[Food]


class LineMatch(_Frozen):
    line_index: int
    item_id: int


class FoodMapping(_Frozen):
    food_name: str
    size_category_id: int | None
