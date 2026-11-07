"""DocumentReader protocol and LocalDocumentReader. Owner: Member 3, Task 10.

Routes depend on get_document_reader(), never on OCR code directly, so tests
can swap in the `fake_reader` fixture and need no Tesseract.
"""

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml

from app.config import get_settings
from app.documents import barcode, fuzzy, ocr
from app.documents.food_parser import parse_foods
from app.documents.receipt_parser import parse_receipt
from app.documents.schemas import DocumentError, Food, FoodList, FoodMapping, LineMatch, ReceiptData, ReceiptLine
from app.documents.text import fold

ABBREVIATIONS_PATH = Path(__file__).resolve().parents[3] / "data" / "abbreviations.yaml"

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
PDF_TYPE = "application/pdf"
TEXT_TYPE = "text/plain"


@runtime_checkable
class DocumentReader(Protocol):
    def read_receipt(self, content: bytes, media_type: str) -> ReceiptData: ...

    def read_foods(self, content: bytes, media_type: str) -> FoodList: ...

    def match_lines(self, lines: Sequence[ReceiptLine], items: Sequence[Mapping]) -> list[LineMatch]: ...

    def map_foods(self, foods: Sequence[Food], leaves: Sequence[Mapping]) -> list[FoodMapping]: ...


class LocalDocumentReader:
    """Reads documents on this machine with Tesseract, OpenCV and rapidfuzz."""

    def __init__(self, settings, abbreviations: Mapping[str, str]) -> None:
        self.settings = settings
        self.abbreviations = dict(abbreviations)

    def read_receipt(self, content: bytes, media_type: str) -> ReceiptData:
        if media_type not in IMAGE_TYPES:
            return parse_receipt(self._to_text(content, media_type, allow_text=False))
        return self._read_receipt_photo(content).model_copy(update={"barcode": barcode.read_code(content)})

    def read_foods(self, content: bytes, media_type: str) -> FoodList:
        return parse_foods(self._to_text(content, media_type, allow_text=True))

    def match_lines(self, lines: Sequence[ReceiptLine], items: Sequence[Mapping]) -> list[LineMatch]:
        return fuzzy.match_lines(lines, items, self.abbreviations, self.settings.OCR_MIN_MATCH_SCORE)

    def map_foods(self, foods: Sequence[Food], leaves: Sequence[Mapping]) -> list[FoodMapping]:
        return fuzzy.map_foods(foods, leaves, self.settings.OCR_MIN_MATCH_SCORE)

    def _read_receipt_photo(self, content: bytes) -> ReceiptData:
        """Read the receipt, and read it again if its products don't add up.

        A receipt checks itself, so a second look only costs time on a bad read.
        That look skips the crop, which a shadow across the paper can cut short.
        """
        first = parse_receipt(ocr.image_to_text(content, self.settings, flattened=True))
        if _adds_up(first):
            return first
        try:
            second = parse_receipt(ocr.image_to_text(content, self.settings, flattened=True, cropped=False))
        except DocumentError:
            return first
        return _better_reading(first, second)

    def _to_text(self, content: bytes, media_type: str, allow_text: bool) -> str:
        if media_type in IMAGE_TYPES:
            return ocr.image_to_text(content, self.settings)
        if media_type == PDF_TYPE:
            return ocr.pdf_to_text(content, self.settings)
        if allow_text and media_type == TEXT_TYPE:
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise DocumentError("The text isn't valid UTF-8") from error
        raise DocumentError(f"Unsupported file type: {media_type}")


def _adds_up(data: ReceiptData) -> bool:
    return bool(data.lines) and sum(line.line_total for line in data.lines) == data.total


def _better_reading(first: ReceiptData, second: ReceiptData) -> ReceiptData:
    """The reading that adds up, or else has more products, plus anything only the other found."""
    use_second = _adds_up(second) or len(second.lines) > len(first.lines)
    best, other = (second, first) if use_second else (first, second)
    details = ("store_name", "purchased_at", "total", "identifier", "unique_id")
    return best.model_copy(update={name: getattr(best, name) or getattr(other, name) for name in details})


def load_abbreviations(path: Path = ABBREVIATIONS_PATH) -> dict[str, str]:
    """Read data/abbreviations.yaml as {folded short form: full words}."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {fold(str(short)): str(full) for short, full in data.items()}


@lru_cache
def get_document_reader() -> DocumentReader:
    """FastAPI dependency. Tests override it with the `fake_reader` fixture."""
    return LocalDocumentReader(get_settings(), load_abbreviations())
