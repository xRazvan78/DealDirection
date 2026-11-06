"""Task 10, step 1: how well do the OCR engines read real receipts?

Runs every photo in a folder through the app's own crop and OCR with
RapidOCR and with Tesseract (--psm 4 and --psm 6), parses each result, and
prints a table to paste into the team chat. The OCR text is saved next to the
photos (in ocr_results/), never in the repo, because receipts can hold
personal data.

Usage, from the repository root:
    uv run python scripts/ocr_check.py "C:/path/to/receipt photos"
    uv run python scripts/ocr_check.py "C:/path/to/receipt photos" --engine rapidocr

Then open each ocr_results/*.txt beside its photo and count how many item
lines are readable.
"""

import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from app.config import get_settings
from app.documents.ocr import image_to_text
from app.documents.receipt_parser import parse_receipt
from app.documents.schemas import DocumentError

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
RUNS = {
    "rapidocr": [("rapidocr", None)],
    "tesseract": [("tesseract", 4), ("tesseract", 6)],
}


def main(folder: Path, engine: str) -> None:
    photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in PHOTO_SUFFIXES)
    if not photos:
        sys.exit(f"No .jpg, .jpeg, .png or .webp photos directly inside {folder}")

    out = folder / "ocr_results"
    out.mkdir(exist_ok=True)
    base = get_settings()
    runs = RUNS[engine] if engine != "both" else RUNS["rapidocr"] + RUNS["tesseract"]

    print("| Photo | Engine | Seconds | Store | Date | Total | Items |")
    print("|---|---|---|---|---|---|---|")
    for photo in photos:
        content = photo.read_bytes()
        for name, psm in runs:
            label = name if psm is None else f"{name} psm{psm}"
            settings = SimpleNamespace(
                OCR_ENGINE=name,
                OCR_RAPID_LANG=base.OCR_RAPID_LANG,
                TESSERACT_CMD=base.TESSERACT_CMD,
                OCR_LANG=base.OCR_LANG,
                OCR_PSM=psm or base.OCR_PSM,
            )
            start = time.perf_counter()
            try:
                text = image_to_text(content, settings)
            except DocumentError as error:
                print(f"| {photo.name} | {label} | - | failed: {error} | | | |")
                continue
            seconds = time.perf_counter() - start

            (out / f"{photo.stem}.{label.replace(' ', '.')}.txt").write_text(text, encoding="utf-8")
            receipt = parse_receipt(text)
            date = receipt.purchased_at.strftime("%d.%m.%Y") if receipt.purchased_at else "missing"
            total = receipt.total if receipt.total is not None else "missing"
            items = "; ".join(f"{line.raw_text} {line.line_total}" for line in receipt.lines) or "none"
            print(
                f"| {photo.name} | {label} | {seconds:.1f} | {receipt.store_name or 'missing'} "
                f"| {date} | {total} | {items} |"
            )

    print(f"\nOCR text saved in {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--engine", choices=["both", "rapidocr", "tesseract"], default="both")
    args = parser.parse_args()
    if not args.folder.is_dir():
        sys.exit(f"Not a folder: {args.folder}")
    main(args.folder, args.engine)
