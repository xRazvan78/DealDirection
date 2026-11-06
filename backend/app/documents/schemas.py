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
    lines: list[ReceiptLine]


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
