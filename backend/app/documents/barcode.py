"""read_code(): the barcode or QR code on a receipt. Owner: Member 3, Task 10.

A decoded code has a checksum, so unlike OCR it can't quietly lose a digit. The
digits printed beside it are often worn away, and some receipts print none.
"""

import cv2
import numpy as np
import zxingcpp

# A code's bars can be too thin to read at the photo's size, or too blurred
# once enlarged, so each size is tried. Which one works differs by photo.
SCALES = (1, 2, 3)
MIN_LENGTH = 8  # shorter "codes" are noise, not a receipt's identifier


def read_code(content: bytes) -> str | None:
    """The longest code in the photo, or None if there isn't a readable one."""
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None

    for scale in SCALES:
        enlarged = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        codes = [code.text for code in zxingcpp.read_barcodes(enlarged) if code.valid]
        readable = [text for text in codes if len(text) >= MIN_LENGTH]
        if readable:
            return max(readable, key=len)
    return None
