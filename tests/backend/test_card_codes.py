"""Loyalty cards: brands, reading codes from photos, redrawing them, guessing the brand."""

import io

import numpy as np
import pytest
import zxingcpp
from PIL import Image

from app.cards.brands import BRANDS, brand_by_id
from app.cards.codes import Code, CodeError, decode, draw_svg, guess_brand

QR_TEXT = "https://example.com/card?id=4812345678901"
EAN13_TEXT = "2401234567891"


def code_photo(text: str, fmt, angle: float = 0, background=(40, 110, 200), fmt_name: str = "JPEG") -> bytes:
    """A code printed on a white card, photographed on a coloured table at an angle."""
    code = Image.fromarray(np.array(zxingcpp.write_barcode_to_image(zxingcpp.create_barcode(text, fmt), scale=6))).convert("RGB")
    card = Image.new("RGB", (code.width + 120, code.height + 160), "white")
    card.paste(code, (60, 60))
    card = card.rotate(angle, expand=True, fillcolor=background)
    photo = Image.new("RGB", (card.width + 300, card.height + 300), background)
    photo.paste(card, (150, 150))
    buffer = io.BytesIO()
    photo.save(buffer, fmt_name)
    return buffer.getvalue()


# --- Brands -----------------------------------------------------------------


def test_brands_cover_the_supported_supermarkets() -> None:
    assert [b.id for b in BRANDS] == ["lidl", "kaufland", "auchan", "carrefour", "mega-image", "profi", "penny"]
    assert all(b.colour.startswith("#") and len(b.colour) == 7 for b in BRANDS)


def test_brand_by_id() -> None:
    assert brand_by_id("kaufland").name == "Kaufland"
    assert brand_by_id("nope") is None


# --- Reading codes ----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "fmt", "name"),
    [
        (QR_TEXT, zxingcpp.BarcodeFormat.QRCode, "qr"),
        (EAN13_TEXT, zxingcpp.BarcodeFormat.EAN13, "ean13"),
        ("96385074", zxingcpp.BarcodeFormat.EAN8, "ean8"),
        ("KAUF-00012345", zxingcpp.BarcodeFormat.Code128, "code128"),
        ("AUCHAN123", zxingcpp.BarcodeFormat.Code39, "code39"),
    ],
)
def test_reads_each_supported_format_from_a_photo(text, fmt, name) -> None:
    assert decode(code_photo(text, fmt)) == Code(text=text, format=name)


def test_reads_a_tilted_photo() -> None:
    assert decode(code_photo(QR_TEXT, zxingcpp.BarcodeFormat.QRCode, angle=25)).text == QR_TEXT


def test_reads_png_and_webp() -> None:
    assert decode(code_photo(EAN13_TEXT, zxingcpp.BarcodeFormat.EAN13, fmt_name="PNG")).format == "ean13"
    assert decode(code_photo(EAN13_TEXT, zxingcpp.BarcodeFormat.EAN13, fmt_name="WEBP")).format == "ean13"


def test_photo_without_a_code_gives_none() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buffer, "JPEG")

    assert decode(buffer.getvalue()) is None


def test_unsupported_code_type_gives_none() -> None:
    # A Data Matrix code is real, but not one of the loyalty card formats.
    assert decode(code_photo("12345", zxingcpp.BarcodeFormat.DataMatrix)) is None


def test_bad_bytes_raise() -> None:
    with pytest.raises(CodeError):
        decode(b"not an image")


# --- Redrawing codes --------------------------------------------------------


@pytest.mark.parametrize(("text", "name"), [(QR_TEXT, "qr"), (EAN13_TEXT, "ean13"), ("KAUF-00012345", "code128")])
def test_supported_codes_redraw_as_svg(text, name) -> None:
    svg = draw_svg(text, name)

    assert svg.lstrip().startswith(("<?xml", "<svg"))
    assert "<svg" in svg


def test_redraw_rejects_an_invalid_code() -> None:
    with pytest.raises(CodeError):
        draw_svg("2401234567893", "ean13")  # wrong check digit
    with pytest.raises(CodeError):
        draw_svg("123", "datamatrix")  # not a supported format


# --- Guessing the brand -----------------------------------------------------


def test_brand_name_printed_on_the_card() -> None:
    assert guess_brand("4812345678901", "KAUFLAND CARD\nNr. client 123") == "kaufland"


def test_brand_in_the_code_contents() -> None:
    assert guess_brand("https://www.lidl.ro/plus/abc", "") == "lidl"


def test_diacritics_and_spacing_are_ignored() -> None:
    assert guess_brand("123", "Card fidelitate MEGA  IMAGE") == "mega-image"


def test_no_brand_gives_none() -> None:
    assert guess_brand("4812345678901", "Card de fidelitate") is None


def test_two_brands_give_no_guess() -> None:
    # "Penny" and "Lidl" both appear: don't guess wrong at the till.
    assert guess_brand("123", "Penny si Lidl") is None


def test_brand_must_be_a_whole_word() -> None:
    # "profit" isn't "Profi".
    assert guess_brand("123", "profit maxim") is None
