"""Task 10: fuzzy matching, food mapping, OCR and the document reader."""

from decimal import Decimal

from app.documents.fuzzy import map_foods, match_lines, score_line
from app.documents.schemas import Food, LineMatch, ReceiptLine
from app.documents.text import fold

MIN_SCORE = 70
ABBREVIATIONS = {"alb": "albalact", "pn": "paine"}

MILK = {"id": 1, "name": "Lapte integral Albalact 3.5% grasime 1 l", "brand": None, "expected_price": Decimal("7.99")}
BREAD = {"id": 2, "name": "Paine alba feliata 500 g", "brand": None, "expected_price": Decimal("4.50")}


def line(text: str, total: str, qty: str = "1") -> ReceiptLine:
    return ReceiptLine(raw_text=text, quantity=Decimal(qty), line_total=Decimal(total))


# --- fold -------------------------------------------------------------------


def test_fold() -> None:
    assert fold("Brânză de Țară") == "branza de tara"


# --- score_line -------------------------------------------------------------


def test_abbreviation_scores_over_70_against_milk() -> None:
    assert score_line(line("LAPTE ALB 3,5% 1L", "7.99"), MILK, ABBREVIATIONS) > 70


def test_closer_price_scores_higher() -> None:
    close = score_line(line("LAPTE ALB 3,5% 1L", "8.10"), MILK, ABBREVIATIONS)
    far = score_line(line("LAPTE ALB 3,5% 1L", "12.00"), MILK, ABBREVIATIONS)

    assert close > far


def test_price_uses_unit_price() -> None:
    # 3 x 7.99 is the right unit price, so it scores like a single carton.
    single = score_line(line("LAPTE ALB 3,5% 1L", "7.99"), MILK, ABBREVIATIONS)
    three = score_line(line("LAPTE ALB 3,5% 1L", "23.97", qty="3"), MILK, ABBREVIATIONS)

    assert single == three


def test_unrelated_line_scores_low() -> None:
    assert score_line(line("DETERGENT ARIEL 2KG", "7.99"), MILK, ABBREVIATIONS) < MIN_SCORE


def test_brand_item_rejects_another_brand() -> None:
    zuzu = {**MILK, "id": 3, "name": "Lapte integral Zuzu 3.5% 1 l", "brand": "Zuzu"}

    assert score_line(line("LAPTE ALB 3,5% 1L", "7.99"), zuzu, ABBREVIATIONS) == 0
    assert score_line(line("LAPTE ZUZU 3,5% 1L", "7.99"), zuzu, ABBREVIATIONS) > MIN_SCORE


# --- match_lines ------------------------------------------------------------


def test_each_line_and_item_is_used_once() -> None:
    lines = [line("LAPTE ALB 3,5% 1L", "7.99"), line("LAPTE ALB 3,5% 1L", "7.99"), line("PN ALBA FELIATA 500G", "4.50")]

    matches = match_lines(lines, [MILK, BREAD], ABBREVIATIONS, MIN_SCORE)

    assert sorted(matches, key=lambda m: m.item_id) == [LineMatch(line_index=0, item_id=1), LineMatch(line_index=2, item_id=2)]


def test_best_score_wins() -> None:
    # The second line has the exact price, so it takes the milk.
    lines = [line("LAPTE ALB 3,5% 1L", "11.00"), line("LAPTE ALB 3,5% 1L", "7.99")]

    assert match_lines(lines, [MILK], ABBREVIATIONS, MIN_SCORE) == [LineMatch(line_index=1, item_id=1)]


def test_low_scores_are_ignored() -> None:
    lines = [line("DETERGENT ARIEL 2KG", "40.00")]

    assert match_lines(lines, [MILK, BREAD], ABBREVIATIONS, MIN_SCORE) == []


# --- map_foods --------------------------------------------------------------

LEAVES = [
    {"id": 10, "path": ["Carne de pui", "Piept", "1 kg"], "aliases": ["piept de pui", "pui file"]},
    {"id": 11, "path": ["Lapte", "3.5%", "1 l"], "aliases": ["lapte"]},
]


def food(name: str) -> Food:
    return Food(name=name, amount=Decimal("200"), unit="g", per_day=True)


def test_map_foods_uses_aliases() -> None:
    mappings = map_foods([food("piept de pui"), food("Pui file")], LEAVES, MIN_SCORE)

    assert [m.size_category_id for m in mappings] == [10, 10]


def test_map_foods_ignores_diacritics() -> None:
    leaves = [{"id": 12, "path": ["Brânză", "Telemea", "1 kg"], "aliases": ["branza telemea"]}]

    assert map_foods([food("brânză telemea")], leaves, MIN_SCORE)[0].size_category_id == 12


def test_unknown_food_has_no_category() -> None:
    mapping = map_foods([food("ciocolata")], LEAVES, MIN_SCORE)[0]

    assert (mapping.food_name, mapping.size_category_id) == ("ciocolata", None)


# --- OCR and PDFs -----------------------------------------------------------

import io  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
import pytesseract  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.documents import ocr  # noqa: E402
from app.documents.schemas import DocumentError  # noqa: E402

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_SETTINGS = SimpleNamespace(
    OCR_ENGINE="tesseract", TESSERACT_CMD=TESSERACT_CMD, OCR_LANG="ron+eng", OCR_PSM=4, OCR_RAPID_LANG="ro"
)
RAPID_SETTINGS = SimpleNamespace(**{**vars(OCR_SETTINGS), "OCR_ENGINE": "rapidocr"})


def tesseract_installed() -> bool:
    for cmd in (TESSERACT_CMD, "tesseract"):
        pytesseract.pytesseract.tesseract_cmd = cmd
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            continue
    return False


needs_tesseract = pytest.mark.skipif(not tesseract_installed(), reason="Tesseract isn't installed")


def text_image(text: str, fmt: str = "PNG") -> bytes:
    image = Image.new("RGB", (900, 220), "white")
    ImageDraw.Draw(image).text((40, 70), text, fill="black", font=ImageFont.load_default(size=64))
    buffer = io.BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def text_pdf(text: str) -> bytes:
    """A one-page PDF with a real text layer, written by hand."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n%s\nendobj\n" % (number, body))
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return out.getvalue()


@needs_tesseract
def test_generated_total_image_is_read() -> None:
    text = ocr.image_to_text(text_image("TOTAL 123.45"), OCR_SETTINGS)

    assert "TOTAL" in text.upper()
    assert "123.45" in text.replace(",", ".")


@needs_tesseract
def test_scanned_pdf_is_read_with_ocr() -> None:
    buffer = io.BytesIO()
    Image.open(io.BytesIO(text_image("TOTAL 123.45"))).save(buffer, "PDF", resolution=150)

    assert "123.45" in ocr.pdf_to_text(buffer.getvalue(), OCR_SETTINGS).replace(",", ".")


def test_pdf_with_text_skips_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_ocr(*args, **kwargs):
        raise AssertionError("OCR shouldn't run for a PDF with text")

    monkeypatch.setattr(ocr, "_ocr", no_ocr)

    assert "200g piept de pui zilnic" in ocr.pdf_to_text(text_pdf("200g piept de pui zilnic"), OCR_SETTINGS)


def test_bad_image_bytes_raise() -> None:
    with pytest.raises(DocumentError):
        ocr.image_to_text(b"not an image", OCR_SETTINGS)


def test_bad_pdf_bytes_raise() -> None:
    with pytest.raises(DocumentError):
        ocr.pdf_to_text(b"not a pdf", OCR_SETTINGS)


def test_timeout_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(*args, **kwargs):
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(pytesseract, "image_to_string", slow)

    with pytest.raises(DocumentError):
        ocr.image_to_text(text_image("TOTAL 1.00"), OCR_SETTINGS)


# --- The reader -------------------------------------------------------------

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.documents.reader import DocumentReader, LocalDocumentReader, get_document_reader, load_abbreviations  # noqa: E402
from app.documents.schemas import FoodList, ReceiptData  # noqa: E402

READER_SETTINGS = SimpleNamespace(**vars(OCR_SETTINGS), OCR_MIN_MATCH_SCORE=MIN_SCORE)


def local_reader() -> LocalDocumentReader:
    return LocalDocumentReader(READER_SETTINGS, ABBREVIATIONS)


def test_local_reader_is_a_document_reader() -> None:
    assert isinstance(local_reader(), DocumentReader)


def test_read_foods_from_text() -> None:
    foods = local_reader().read_foods("Plan 7 zile\n200g piept de pui zilnic".encode(), "text/plain")

    assert foods.plan_days == 7
    assert foods.foods[0].name == "piept de pui"


def test_read_foods_from_pdf() -> None:
    foods = local_reader().read_foods(text_pdf("200g piept de pui zilnic"), "application/pdf")

    assert foods.foods[0].name == "piept de pui"


@needs_tesseract
def test_read_receipt_from_image() -> None:
    receipt = local_reader().read_receipt(text_image("TOTAL 123.45"), "image/png")

    assert receipt.total == Decimal("123.45")


def test_unsupported_type_raises() -> None:
    with pytest.raises(DocumentError):
        local_reader().read_receipt(b"hello", "application/zip")


def test_text_that_isnt_utf8_raises() -> None:
    with pytest.raises(DocumentError):
        local_reader().read_foods(b"\xff\xfe\xfa", "text/plain")


def test_reader_uses_settings_min_score() -> None:
    lines = [line("LAPTE ALB 3,5% 1L", "7.99")]

    assert local_reader().match_lines(lines, [MILK]) == [LineMatch(line_index=0, item_id=1)]
    strict = LocalDocumentReader(SimpleNamespace(**{**vars(READER_SETTINGS), "OCR_MIN_MATCH_SCORE": 101}), ABBREVIATIONS)
    assert strict.match_lines(lines, [MILK]) == []


def test_project_abbreviations_file_loads() -> None:
    assert isinstance(load_abbreviations(), dict)


def test_fake_reader_replaces_the_real_one(fake_reader) -> None:
    fake_reader.receipt = ReceiptData(store_name="Auchan", purchased_at=None, total=Decimal("1"), lines=[])

    app = FastAPI()

    @app.get("/store")
    def store(reader: DocumentReader = Depends(get_document_reader)) -> dict:
        return {"store": reader.read_receipt(b"", "image/png").store_name}

    app.dependency_overrides[get_document_reader] = lambda: fake_reader
    assert TestClient(app).get("/store").json() == {"store": "Auchan"}


def test_fake_reader_can_fail(fake_reader) -> None:
    fake_reader.error = DocumentError("unreadable")

    with pytest.raises(DocumentError):
        fake_reader.read_receipt(b"", "image/png")


def test_fake_reader_records_calls_and_matches_for_real(fake_reader) -> None:
    fake_reader.foods = FoodList(plan_days=None, foods=[])

    fake_reader.read_foods(b"x", "text/plain")
    matches = fake_reader.match_lines([line("LAPTE ALB 3,5% 1L", "7.99")], [MILK])

    assert fake_reader.calls == ["read_foods", "match_lines"]
    assert matches == [LineMatch(line_index=0, item_id=1)]


# --- Finding the receipt in a photo -----------------------------------------

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.documents import reader as reader_module  # noqa: E402


def receipt_on_wood() -> np.ndarray:
    """A white 'receipt' on an orange, streaky 'table', like a real photo."""
    rng = np.random.default_rng(0)
    photo = np.zeros((1600, 740, 3), dtype=np.uint8)
    photo[:] = (60, 120, 190)  # BGR orange-brown
    photo[:, :, 1] += rng.integers(0, 40, size=(1600, 1), dtype=np.uint8)  # grain
    photo[550:1550, 100:550] = (235, 235, 235)
    return photo


def test_receipt_is_cropped_out_of_a_busy_background() -> None:
    cropped = ocr._find_receipt(receipt_on_wood())

    height, width = cropped.shape[:2]
    assert 950 <= height <= 1050
    assert 420 <= width <= 480


def test_photo_without_a_clear_receipt_is_kept_whole() -> None:
    plain = np.full((400, 300, 3), 128, dtype=np.uint8)

    assert ocr._find_receipt(plain).shape == plain.shape


def test_dark_blue_receipt_is_cropped_out_of_a_dark_table() -> None:
    photo = np.zeros((1600, 740, 3), dtype=np.uint8)
    photo[:] = (30, 60, 95)  # BGR, a warm wood in low light
    photo[550:1550, 100:550] = (110, 80, 60)  # too dim and too blue to pass as white paper

    cropped = ocr._crop_to_paper(photo)

    assert 950 <= cropped.shape[0] <= 1050
    assert 420 <= cropped.shape[1] <= 480


def test_colours_too_alike_to_tell_apart_keep_the_photo_whole() -> None:
    photo = np.full((400, 300, 3), 70, dtype=np.uint8)
    photo[:, :, 0] = np.tile(np.arange(70, 70 + 300) % 256, (400, 1))

    assert ocr._crop_to_paper(photo).shape[0] >= 360


def page_with_ink(brightness: np.ndarray) -> np.ndarray:
    """A grey page lit by `brightness`, with a dark ink stroke at x=100."""
    page = np.broadcast_to(brightness[:, None], (brightness.size, 300)).astype(np.float32).copy()
    page[:, 100:104] *= 0.2
    return cv2.cvtColor(page.astype(np.uint8), cv2.COLOR_GRAY2BGR)


def test_flatten_removes_a_shadow_and_keeps_the_ink() -> None:
    flat = ocr.flatten(page_with_ink(np.linspace(230, 70, 600)))
    paper, ink = flat[:, 200], flat[:, 101]

    assert paper.max() - paper.min() < 30  # was 160 across the page
    assert (paper[100:500].astype(int) - ink[100:500].astype(int)).min() > 120


def test_flatten_gives_a_blue_and_a_white_receipt_the_same_paper() -> None:
    white = np.full((300, 300, 3), 235, dtype=np.uint8)
    blue = np.full((300, 300, 3), (170, 120, 90), dtype=np.uint8)

    assert abs(int(ocr.flatten(white).mean()) - int(ocr.flatten(blue).mean())) < 3


def test_flatten_keeps_the_photos_size() -> None:
    photo = np.full((3000, 2000), 200, dtype=np.uint8)

    assert ocr.flatten(photo).shape == photo.shape


# --- Reading a receipt photo twice if it doesn't add up ---------------------

GOOD = "CHIPS 7,99 B\nSUC 2,00 A\nTOTAL 9,99"
SHORT = "CHIPS 7,99 B\nTOTAL 9,99"


def reads(monkeypatch, *texts: str) -> list[dict]:
    """Make OCR return `texts` in turn. Returns the options of each call."""
    calls: list[dict] = []
    answers = iter(texts)

    def fake(content, settings, **options):
        calls.append(options)
        return next(answers)

    monkeypatch.setattr(ocr, "image_to_text", fake)
    monkeypatch.setattr(reader_module.barcode, "read_code", lambda content: None)
    return calls


def test_a_receipt_that_adds_up_is_read_once(monkeypatch) -> None:
    calls = reads(monkeypatch, GOOD)

    data = local_reader().read_receipt(b"", "image/jpeg")

    assert len(data.lines) == 2
    assert calls == [{"flattened": True}]


def test_a_receipt_that_does_not_add_up_is_read_again_without_the_crop(monkeypatch) -> None:
    calls = reads(monkeypatch, SHORT, GOOD)

    data = local_reader().read_receipt(b"", "image/jpeg")

    assert [line.raw_text for line in data.lines] == ["CHIPS", "SUC"]
    assert calls[1] == {"flattened": True, "cropped": False}


def test_neither_reading_adds_up_keeps_the_one_with_more_products(monkeypatch) -> None:
    reads(monkeypatch, "CHIPS 7,99 B\nSUC 2,00 A\nTOTAL 50,00", "CHIPS 7,99 B\nTOTAL 50,00")

    assert len(local_reader().read_receipt(b"", "image/jpeg").lines) == 2


def test_details_only_the_other_reading_found_are_kept(monkeypatch) -> None:
    first = f"{SHORT}\nDATA:06/11/2026\nBF.00061\nID UNIC:60010827022026110612373602640061"
    reads(monkeypatch, first, f"LIDL\n{GOOD}")

    data = local_reader().read_receipt(b"", "image/jpeg")

    assert (data.store_name, len(data.lines)) == ("Lidl", 2)
    assert data.unique_id == "60010827022026110612373602640061"


def test_a_failed_second_look_keeps_the_first_reading(monkeypatch) -> None:
    answers = iter([SHORT])

    def fake(content, settings, **options):
        text = next(answers, None)
        if text is None:
            raise DocumentError("too slow")
        return text

    monkeypatch.setattr(ocr, "image_to_text", fake)
    monkeypatch.setattr(reader_module.barcode, "read_code", lambda content: None)

    assert len(local_reader().read_receipt(b"", "image/jpeg").lines) == 1


def test_a_failed_first_look_is_an_error(monkeypatch) -> None:
    def fake(content, settings, **options):
        raise DocumentError("unreadable")

    monkeypatch.setattr(ocr, "image_to_text", fake)

    with pytest.raises(DocumentError):
        local_reader().read_receipt(b"", "image/jpeg")


@pytest.mark.parametrize("width", [450, 1600, 3300])
def test_clean_resizes_to_a_fixed_width_in_greyscale(width: int) -> None:
    photo = np.full((width * 2, width, 3), 200, dtype=np.uint8)

    cleaned = ocr._clean(photo, find_receipt=False)

    assert cleaned.ndim == 2
    assert cleaned.shape[1] == ocr.TARGET_WIDTH


# --- RapidOCR ---------------------------------------------------------------

import time  # noqa: E402


def box(x: float, y: float, w: float = 100, h: float = 20) -> list[list[float]]:
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def test_boxes_are_grouped_into_lines_left_to_right() -> None:
    boxes = [box(400, 101), box(10, 100), box(10, 140), box(12, 180, h=22), box(400, 183)]
    texts = ["7,99 B", "Chips preparate", "SUBTOTAL", "TOTAL", "25,97"]

    assert ocr._boxes_to_text(boxes, texts) == "Chips preparate  7,99 B\nSUBTOTAL\nTOTAL  25,97"


def test_slightly_tilted_rows_stay_separate() -> None:
    # Each row drifts 6 px down to the right, less than half a line height.
    boxes = [box(10, 100), box(400, 106), box(10, 130), box(400, 136)]
    texts = ["A", "1,00", "B", "2,00"]

    assert ocr._boxes_to_text(boxes, texts) == "A  1,00\nB  2,00"


def test_a_tilted_photo_keeps_each_name_with_its_price() -> None:
    # Boxes turned 3 degrees: the price sits 21 px lower than its name, a whole
    # line away, and the next row's name is nearer to it than its own.
    def tilted(x: float, y: float) -> list[list[float]]:
        slope = 0.0524  # tan(3 degrees)
        width, height = 200, 24
        return [
            [x, y + x * slope],
            [x + width, y + (x + width) * slope],
            [x + width, y + height + (x + width) * slope],
            [x, y + height + x * slope],
        ]

    boxes = [tilted(10, 100), tilted(400, 100), tilted(10, 130), tilted(400, 130)]
    texts = ["A", "1,00", "B", "2,00"]

    assert ocr._boxes_to_text(boxes, texts) == "A  1,00\nB  2,00"


def test_no_boxes_gives_empty_text() -> None:
    assert ocr._boxes_to_text([], []) == ""


def test_rapidocr_reads_the_generated_total_image() -> None:
    text = ocr.image_to_text(text_image("TOTAL 123.45"), RAPID_SETTINGS)

    assert "TOTAL" in text.upper()
    assert "123.45" in text.replace(",", ".")


def test_rapidocr_timeout_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow_engine(language):
        return lambda image: time.sleep(2)

    monkeypatch.setattr(ocr, "_rapid_engine", slow_engine)
    monkeypatch.setattr(ocr, "OCR_TIMEOUT_SECONDS", 0.1)

    with pytest.raises(DocumentError):
        ocr.image_to_text(text_image("TOTAL 1.00"), RAPID_SETTINGS)


def test_unknown_engine_raises() -> None:
    settings = SimpleNamespace(**{**vars(OCR_SETTINGS), "OCR_ENGINE": "magic"})

    with pytest.raises(DocumentError):
        ocr.image_to_text(text_image("TOTAL 1.00"), settings)


def test_settings_default_to_rapidocr(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@localhost/x")
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.delenv("OCR_ENGINE", raising=False)

    settings = Settings(_env_file=None)

    assert (settings.OCR_ENGINE, settings.OCR_RAPID_LANG) == ("rapidocr", "ro")
