"""Read a loyalty card's code from a photo, redraw it cleanly, and guess the brand.

Uses zxing-cpp, which reads and writes QR codes and barcodes locally. Only the
formats loyalty cards use are accepted. A redrawn code is sharp at any size,
which a till scanner reads far better than a photo of the card.
"""

import re
from dataclasses import dataclass

import cv2
import numpy as np
import zxingcpp

from app.cards.brands import BRANDS
from app.textutil import fold

# Our name for each format -> zxing-cpp's format.
FORMATS = {
    "qr": zxingcpp.BarcodeFormat.QRCode,
    "ean13": zxingcpp.BarcodeFormat.EAN13,
    "ean8": zxingcpp.BarcodeFormat.EAN8,
    "upca": zxingcpp.BarcodeFormat.UPCA,
    "code128": zxingcpp.BarcodeFormat.Code128,
    "code39": zxingcpp.BarcodeFormat.Code39,
}
# zxing-cpp's printed name for a format it read -> our name.
_READ_NAMES = {"QR Code": "qr", "EAN-13": "ean13", "EAN-8": "ean8", "UPC-A": "upca", "Code 128": "code128", "Code 39": "code39"}
_LINEAR = {"ean13", "ean8", "upca", "code128", "code39"}


class CodeError(Exception):
    """The image couldn't be read, or the code can't be drawn."""


@dataclass(frozen=True)
class Code:
    text: str
    format: str  # a key of FORMATS


def decode(content: bytes) -> Code | None:
    """The first supported code in the photo, or None if there isn't one."""
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise CodeError("The file isn't a readable image")

    for found in zxingcpp.read_barcodes(image, formats=tuple(FORMATS.values())):
        name = _READ_NAMES.get(str(found.format))
        if name and found.text:
            return Code(found.text, name)
    return None


def draw_svg(text: str, format_name: str) -> str:
    """A clean SVG of the code. Barcodes show their number underneath."""
    fmt = FORMATS.get(format_name)
    if fmt is None:
        raise CodeError(f"Unsupported code format: {format_name}")
    try:
        barcode = zxingcpp.create_barcode(text, fmt)
    except ValueError as error:  # e.g. an EAN-13 with a wrong check digit
        raise CodeError(str(error)) from error
    return zxingcpp.write_barcode_to_svg(barcode, add_hrt=format_name in _LINEAR)


def guess_brand(code_text: str, printed_text: str) -> str | None:
    """The brand named on the card or inside its code, if exactly one is.

    Only a suggestion: the client confirms it. Two different brands, or none,
    give no guess, so a card is never filed under the wrong shop silently.
    """
    haystack = " ".join(fold(f"{code_text}\n{printed_text}").split())
    found = {
        brand.id
        for brand in BRANDS
        for word in brand.keywords
        if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", haystack)
    }
    return found.pop() if len(found) == 1 else None
