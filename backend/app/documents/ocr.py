"""image_to_text() and pdf_to_text(): the only file that knows the OCR engine. Owner: Member 3, Task 10.

The OCR_ENGINE setting picks the engine:
- "rapidocr" (default): PaddleOCR models run locally through onnxruntime. On
  real, creased receipt photos it read the store, date, total and items where
  Tesseract read almost nothing.
- "tesseract": the original plan; kept as a fallback.

Both run on this machine; nothing is sent to an outside service.
Images stay in memory and are never written to disk or logged.
"""

import io
import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from functools import lru_cache

import cv2
import numpy as np
import pypdfium2
import pytesseract
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.documents.schemas import DocumentError

OCR_TIMEOUT_SECONDS = 30
PDF_RENDER_SCALE = 300 / 72  # render scanned pages at 300 dpi
TARGET_WIDTH = 1200  # px; about 30 px per character on a 40-column receipt (Tesseract)
SAME_LINE = 0.5  # boxes whose centres differ by under half a box height share a line


def image_to_text(content: bytes, settings) -> str:
    """OCR a photo of a receipt or list.

    `settings` needs OCR_ENGINE, plus OCR_RAPID_LANG for RapidOCR or
    TESSERACT_CMD, OCR_LANG and OCR_PSM for Tesseract.
    """
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise DocumentError("The file isn't a readable image")
    return _ocr(_find_receipt(image), settings)


def pdf_to_text(content: bytes, settings) -> str:
    """Use the PDF's text layer if it has one, otherwise OCR each page."""
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, ValueError, OSError) as error:
        raise DocumentError("The file isn't a readable PDF") from error

    if any(c.isalnum() for c in text):
        return text

    try:
        pdf = pypdfium2.PdfDocument(content)
        pages = [pdf[i].render(scale=PDF_RENDER_SCALE).to_numpy() for i in range(len(pdf))]
    except Exception as error:  # pypdfium2 raises its own error types
        raise DocumentError("The PDF's pages couldn't be rendered") from error

    return "\n".join(_ocr(page, settings) for page in pages)


def _clean(image: np.ndarray, find_receipt: bool = False) -> np.ndarray:
    """Crop and straighten, then greyscale at a fixed width for Tesseract.

    A fixed width keeps receipt letters near the size Tesseract reads best,
    whether the photo is small or 4000 px. Tests on real receipt photos read
    better as plain greyscale than after adaptive thresholding, which left
    large letters hollow, so Tesseract does its own binarisation.
    """
    if find_receipt:
        image = _find_receipt(image)
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    scale = TARGET_WIDTH / grey.shape[1]
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(grey, None, fx=scale, fy=scale, interpolation=interpolation)


def _find_receipt(image: np.ndarray) -> np.ndarray:
    """Crop to the receipt, then flatten it if its four corners are clear."""
    return _straighten_receipt(_crop_to_paper(image))


def _crop_to_paper(image: np.ndarray) -> np.ndarray:
    """Crop to the largest bright, colourless area: the paper.

    This works on wood, cloth or other busy backgrounds where edge finding
    picks up the texture. If no such area is found, the photo is kept whole.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    paper = cv2.inRange(hsv, (0, 0, 120), (180, 60, 255))
    paper = cv2.morphologyEx(paper, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(paper)
    if count < 2:
        return image

    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, width, height, area = stats[largest]
    if area < 0.05 * image.shape[0] * image.shape[1]:
        return image
    return image[y : y + height, x : x + width]


def _straighten_receipt(image: np.ndarray) -> np.ndarray:
    """Crop and flatten the receipt if a large four-cornered outline is found.

    If none is found (the photo is already tight, or the edges are unclear),
    the photo is used as it is.
    """
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(grey, (5, 5), 0), 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(contour) < 0.2 * image_area:
            break
        corners = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(corners) == 4:
            return _warp(image, corners.reshape(4, 2).astype("float32"))
    return image


def _warp(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    # Order corners: top-left, top-right, bottom-right, bottom-left.
    s, d = corners.sum(axis=1), np.diff(corners, axis=1).ravel()
    tl, br, tr, bl = corners[s.argmin()], corners[s.argmax()], corners[d.argmin()], corners[d.argmax()]
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]), target)
    return cv2.warpPerspective(image, matrix, (width, height))


def _ocr(image: np.ndarray, settings) -> str:
    """Read an already-cropped image with the engine named in settings."""
    engine = settings.OCR_ENGINE
    if engine == "rapidocr":
        return _rapidocr(image, settings)
    if engine == "tesseract":
        return _tesseract(_clean(image), settings)
    raise DocumentError(f"Unknown OCR engine: {engine}")


# --- RapidOCR ---------------------------------------------------------------


@lru_cache
def _rapid_engine(language: str):
    """Load the models once per language; the first call takes a second or two."""
    from rapidocr import RapidOCR  # imported here so Tesseract-only use stays light

    logging.getLogger("RapidOCR").setLevel(logging.WARNING)
    return RapidOCR(params={"Rec.lang_type": language})


def _rapidocr(image: np.ndarray, settings) -> str:
    engine = _rapid_engine(settings.OCR_RAPID_LANG)
    # RapidOCR has no timeout of its own, so it runs in a worker thread.
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        result = pool.submit(engine, image).result(timeout=OCR_TIMEOUT_SECONDS)
    except FutureTimeout as error:
        raise DocumentError("Reading the image took too long") from error
    except Exception as error:  # RapidOCR and onnxruntime raise many types
        raise DocumentError("The OCR engine couldn't read the image") from error
    finally:
        pool.shutdown(wait=False)

    boxes = getattr(result, "boxes", None)
    texts = getattr(result, "txts", None)
    if boxes is None or texts is None:
        return ""  # nothing that looks like text
    return _boxes_to_text(boxes, texts)


def _boxes_to_text(boxes: Sequence, texts: Sequence[str]) -> str:
    """Join RapidOCR's separate text boxes into lines, top to bottom.

    A receipt prints the name on the left and the price on the right, and
    RapidOCR returns them as two boxes. Boxes whose vertical centres are close
    form one line, joined left to right with two spaces, the way the receipt
    parser expects.
    """
    pieces = []
    for box, text in zip(boxes, texts):
        points = np.asarray(box, dtype=float)
        ys = points[:, 1]
        pieces.append((ys.mean(), max(ys.max() - ys.min(), 1.0), points[:, 0].min(), text))
    pieces.sort()

    lines: list[list[tuple[float, str]]] = []
    line_centre = line_height = 0.0
    for centre, height, left, text in pieces:
        if not lines or abs(centre - line_centre) > SAME_LINE * line_height:
            lines.append([])
            line_centre, line_height = centre, height
        lines[-1].append((left, text))

    return "\n".join("  ".join(text for _, text in sorted(line)) for line in lines)


# --- Tesseract --------------------------------------------------------------


def _tesseract(image: np.ndarray, settings) -> str:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    try:
        return pytesseract.image_to_string(
            image,
            lang=settings.OCR_LANG,
            config=f"--psm {settings.OCR_PSM}",
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except RuntimeError as error:  # pytesseract's timeout
        raise DocumentError("Reading the image took too long") from error
    except (pytesseract.TesseractError, pytesseract.TesseractNotFoundError, OSError) as error:
        raise DocumentError("The OCR engine couldn't read the image") from error
