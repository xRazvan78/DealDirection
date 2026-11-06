"""Backend fixtures owned by Member 3. Shared fixtures stay in tests/conftest.py.

`fake_reader` replaces the OCR reader for Tasks 11, 12 and 19, so their tests
need no Tesseract and no real photos.
"""

from collections.abc import Iterator, Mapping, Sequence

import pytest

from app.documents import fuzzy
from app.documents.reader import get_document_reader, load_abbreviations
from app.documents.schemas import (
    DocumentError,
    Food,
    FoodList,
    FoodMapping,
    LineMatch,
    ReceiptData,
    ReceiptLine,
)
from app.main import app


class FakeDocumentReader:
    """Returns whatever a test sets, and records which methods were called.

    - Set `receipt` or `foods` to what reading should return.
    - Set `error` to a DocumentError to make reading fail.
    - Set `matches` or `mappings` to fix the matching results; leave them as
      None to use the real fuzzy matching, which needs no OCR engine.
    """

    def __init__(self) -> None:
        self.receipt: ReceiptData | None = None
        self.foods: FoodList | None = None
        self.error: DocumentError | None = None
        self.matches: list[LineMatch] | None = None
        self.mappings: list[FoodMapping] | None = None
        self.min_score = 70
        self.abbreviations = load_abbreviations()
        self.calls: list[str] = []

    def read_receipt(self, content: bytes, media_type: str) -> ReceiptData:
        self.calls.append("read_receipt")
        if self.error:
            raise self.error
        if self.receipt is None:
            raise DocumentError("The fake reader has no receipt set")
        return self.receipt

    def read_foods(self, content: bytes, media_type: str) -> FoodList:
        self.calls.append("read_foods")
        if self.error:
            raise self.error
        if self.foods is None:
            raise DocumentError("The fake reader has no food list set")
        return self.foods

    def match_lines(self, lines: Sequence[ReceiptLine], items: Sequence[Mapping]) -> list[LineMatch]:
        self.calls.append("match_lines")
        if self.matches is not None:
            return self.matches
        return fuzzy.match_lines(lines, items, self.abbreviations, self.min_score)

    def map_foods(self, foods: Sequence[Food], leaves: Sequence[Mapping]) -> list[FoodMapping]:
        self.calls.append("map_foods")
        if self.mappings is not None:
            return self.mappings
        return fuzzy.map_foods(foods, leaves, self.min_score)


@pytest.fixture
def fake_reader() -> Iterator[FakeDocumentReader]:
    """A FakeDocumentReader that the app uses instead of the real one."""
    reader = FakeDocumentReader()
    app.dependency_overrides[get_document_reader] = lambda: reader
    yield reader
    app.dependency_overrides.pop(get_document_reader, None)
