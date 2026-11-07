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
        data = parse_receipt(self._to_text(content, media_type, allow_text=False))
        code = barcode.read_code(content) if media_type in IMAGE_TYPES else None
        return data.model_copy(update={"barcode": code})

    def read_foods(self, content: bytes, media_type: str) -> FoodList:
        return parse_foods(self._to_text(content, media_type, allow_text=True))

    def match_lines(self, lines: Sequence[ReceiptLine], items: Sequence[Mapping]) -> list[LineMatch]:
        return fuzzy.match_lines(lines, items, self.abbreviations, self.settings.OCR_MIN_MATCH_SCORE)

    def map_foods(self, foods: Sequence[Food], leaves: Sequence[Mapping]) -> list[FoodMapping]:
        return fuzzy.map_foods(foods, leaves, self.settings.OCR_MIN_MATCH_SCORE)

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


def load_abbreviations(path: Path = ABBREVIATIONS_PATH) -> dict[str, str]:
    """Read data/abbreviations.yaml as {folded short form: full words}."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {fold(str(short)): str(full) for short, full in data.items()}


@lru_cache
def get_document_reader() -> DocumentReader:
    """FastAPI dependency. Tests override it with the `fake_reader` fixture."""
    return LocalDocumentReader(get_settings(), load_abbreviations())
