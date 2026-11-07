"""Reading a receipt's barcode, on generated images. No real photos needed."""

from decimal import Decimal

import cv2
import numpy as np
import zxingcpp

from app.documents import barcode
from app.documents.reader import LocalDocumentReader
from app.documents.schemas import ReceiptData, ReceiptLine

RECEIPT_CODE = "9264238711852413082267699676"


def photo_of(text: str, kind=zxingcpp.BarcodeFormat.Code128, scale: int = 3) -> bytes:
    image = np.array(zxingcpp.create_barcode(text, kind).to_image(scale=scale), dtype=np.uint8)
    framed = cv2.copyMakeBorder(image, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    return cv2.imencode(".png", framed)[1].tobytes()


def blank_photo() -> bytes:
    return cv2.imencode(".png", np.full((200, 200), 255, dtype=np.uint8))[1].tobytes()


def test_reads_a_receipt_barcode() -> None:
    assert barcode.read_code(photo_of(RECEIPT_CODE)) == RECEIPT_CODE


def test_reads_a_qr_code() -> None:
    assert barcode.read_code(photo_of(RECEIPT_CODE, zxingcpp.BarcodeFormat.QRCode)) == RECEIPT_CODE


def test_bars_too_thin_for_the_photo_are_enlarged() -> None:
    assert barcode.read_code(photo_of(RECEIPT_CODE, scale=1)) == RECEIPT_CODE


def test_a_photo_without_a_code_gives_none() -> None:
    assert barcode.read_code(blank_photo()) is None


def test_a_short_code_is_not_an_identifier() -> None:
    assert barcode.read_code(photo_of("123")) is None


def test_bad_bytes_give_none() -> None:
    assert barcode.read_code(b"not an image") is None


class _TextReader(LocalDocumentReader):
    """Skips OCR, so only the choice of identifier is tested."""

    def __init__(self) -> None:
        pass

    def _to_text(self, content, media_type, allow_text):
        return "CHIPS 7,99 B\nTOTAL 7,99\nID UNIC: 12345678"


def test_barcode_replaces_the_identifier_read_by_ocr() -> None:
    assert _TextReader().read_receipt(photo_of(RECEIPT_CODE), "image/png").identifier == RECEIPT_CODE


def test_ocr_identifier_stays_when_there_is_no_barcode() -> None:
    assert _TextReader().read_receipt(blank_photo(), "image/png").identifier == "12345678"


def test_receipt_data_is_otherwise_unchanged() -> None:
    data = _TextReader().read_receipt(photo_of(RECEIPT_CODE), "image/png")

    assert data.lines == [ReceiptLine(raw_text="CHIPS", quantity=Decimal(1), line_total=Decimal("7.99"))]
    assert isinstance(data, ReceiptData)
