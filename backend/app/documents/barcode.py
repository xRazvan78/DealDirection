"""read_code(): the barcode or QR code on a receipt. Owner: Member 3, Task 10.

A decoded code has a checksum, so unlike OCR it can't quietly lose a digit. The
digits printed beside it are often worn away, and some receipts print none.
"""

import time

import cv2
import numpy as np
import zxingcpp

from app.documents.ocr import flatten

# A code's bars can be too thin to read at the photo's size, or too blurred
# once enlarged, so each size is tried. Which one works differs by photo.
SCALES = (1, 2, 3)
MAX_SIDE = 4000  # px; a photo enlarged further only costs time
MIN_LENGTH = 8  # shorter "codes" are noise, not a receipt's identifier

# On a creased receipt a tilted code may only decode once it's level to the
# degree. Trying every angle costs a few seconds, so it's only the fallback,
# at one size that suits real photos. OpenCV's barcode finder doesn't help
# narrow this down: on a wooden table it picks the wood grain.
TILTS = tuple(sign * degrees for degrees in range(1, 9) for sign in (1, -1))
TILT_SIDE = 3200  # px
TILT_SECONDS = 4  # a photo with no code at all shouldn't hold up the client


def read_code(content: bytes) -> str | None:
    """The longest code in the photo, or None if there isn't a readable one."""
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None

    # Dark or blue paper hides the bars until it's evened out.
    versions = (image, flatten(image))
    for version in versions:
        for scale in SCALES:
            if scale == 1 or max(version.shape) * scale <= MAX_SIDE:
                code = _decode(_resized(version, scale))
                if code:
                    return code

    give_up_at = time.monotonic() + TILT_SECONDS
    for version in versions:
        level = _resized(version, TILT_SIDE / max(version.shape))
        for tilt in TILTS:
            code = _decode(_turned(level, tilt))
            if code or time.monotonic() > give_up_at:
                return code
    return None


def _decode(image: np.ndarray) -> str | None:
    codes = [code.text for code in zxingcpp.read_barcodes(image) if code.valid]
    readable = [text for text in codes if len(text) >= MIN_LENGTH]
    return max(readable, key=len) if readable else None


def _resized(image: np.ndarray, scale: float) -> np.ndarray:
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _turned(image: np.ndarray, degrees: float) -> np.ndarray:
    height, width = image.shape
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), degrees, 1)
    return cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderValue=255)
