"""Task 10: food list and receipt text parsing. No OCR engine needed."""

from decimal import Decimal

from app.documents.food_parser import parse_foods


def only_food(text: str):
    foods = parse_foods(text).foods
    assert len(foods) == 1, foods
    return foods[0]


# --- Food lists -------------------------------------------------------------


def test_daily_food() -> None:
    food = only_food("200g piept de pui zilnic")

    assert (food.name, food.amount, food.unit, food.per_day) == (
        "piept de pui",
        Decimal("200"),
        "g",
        True,
    )


def test_pe_zi_is_daily() -> None:
    assert only_food("150 g orez pe zi").per_day is True


def test_not_daily() -> None:
    food = only_food("1 kg mere")

    assert food.per_day is False
    assert (food.name, food.amount, food.unit) == ("mere", Decimal("1"), "kg")


def test_plan_days() -> None:
    assert parse_foods("Plan 7 zile\n200g piept de pui zilnic").plan_days == 7


def test_no_plan_days() -> None:
    assert parse_foods("200g piept de pui zilnic").plan_days is None


def test_decimal_comma_amount() -> None:
    food = only_food("1,5 l lapte")

    assert (food.amount, food.unit, food.name) == (Decimal("1.5"), "l", "lapte")


def test_units_are_normalised() -> None:
    assert only_food("250 gr branza").unit == "g"
    assert only_food("2 litri apa").unit == "l"
    assert only_food("3 bucati oua").unit == "buc"
    assert only_food("500ml iaurt").unit == "ml"


def test_several_foods_in_one_message() -> None:
    foods = parse_foods("200g piept de pui zilnic, 100g orez pe zi; 1 kg mere").foods

    assert [f.name for f in foods] == ["piept de pui", "orez", "mere"]


def test_bullets_and_diacritics() -> None:
    food = only_food("- 100 g brânză de vaci zilnic.")

    assert food.name == "brânză de vaci"
    assert food.per_day is True


def test_plan_length_words_stay_out_of_names() -> None:
    assert only_food("200g pui zilnic timp de 7 zile").name == "pui"


def test_lines_without_amounts_are_ignored() -> None:
    assert parse_foods("Mic dejun\nBea multa apa").foods == []


# --- Receipts (shared patterns) ---------------------------------------------
# Synthetic text in the usual Romanian fiscal layout. Real receipt fixtures go
# in tests/fixtures/receipts/ once they're photographed and read.

from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from app.documents.receipt_parser import parse_receipt  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "receipts"

AUCHAN_LIKE = """\
AUCHAN ROMANIA SA
Str. Exemplu nr. 1
COD FISCAL RO17233051
0,734 KG x 7,99
BANANE                     5,86 B
2 BUC x 4,50
PAINE ALBA FELIATA         9,00 A
LAPTE ALB 3,5% 1L          7,99 A
SUBTOTAL                  22,85
TOTAL                     22,85
CARD                      22,85
TOTAL TVA                  2,08
05.11.2026 18:42:10
"""


def test_receipt_store_total_and_date() -> None:
    receipt = parse_receipt(AUCHAN_LIKE)

    assert receipt.store_name == "Auchan"
    assert receipt.total == Decimal("22.85")
    assert receipt.purchased_at == datetime(2026, 11, 5, 18, 42, 10)


def test_receipt_lines() -> None:
    lines = parse_receipt(AUCHAN_LIKE).lines

    assert [(l.raw_text, l.quantity, l.line_total) for l in lines] == [
        ("BANANE", Decimal("0.734"), Decimal("5.86")),
        ("PAINE ALBA FELIATA", Decimal("2"), Decimal("9.00")),
        ("LAPTE ALB 3,5% 1L", Decimal("1"), Decimal("7.99")),
    ]


def test_weighed_quantity() -> None:
    lines = parse_receipt("0,734 KG x 7,99\nBANANE 5,86 B\nTOTAL 5,86").lines

    assert lines[0].quantity == Decimal("0.734")


def test_quantity_line_with_its_own_total() -> None:
    lines = parse_receipt("1,000 BUC x 7,99 = 7,99\nLAPTE ZUZU 1L\nTOTAL 7,99").lines

    assert [(l.raw_text, l.quantity, l.line_total) for l in lines] == [
        ("LAPTE ZUZU 1L", Decimal("1.000"), Decimal("7.99")),
    ]


def test_missing_total_is_none() -> None:
    receipt = parse_receipt("CARREFOUR\nLAPTE 7,99\n05/11/2026")

    assert receipt.total is None
    assert receipt.store_name == "Carrefour"


def test_missing_date_is_none() -> None:
    assert parse_receipt("TOTAL 7,99").purchased_at is None


def test_date_without_time_and_iso_date() -> None:
    assert parse_receipt("DATA: 05-11-2026").purchased_at == datetime(2026, 11, 5)
    assert parse_receipt("2026-11-05 09:15").purchased_at == datetime(2026, 11, 5, 9, 15)


def test_unknown_store_is_empty() -> None:
    assert parse_receipt("MAGAZIN XYZ\nTOTAL 1,00").store_name == ""


def test_empty_text_does_not_crash() -> None:
    receipt = parse_receipt("")

    assert (receipt.total, receipt.purchased_at, receipt.lines) == (None, None, [])


# --- Tolerating real OCR output ---------------------------------------------
# Taken from Tesseract's reading of a real Lidl receipt photo.


def test_total_with_stray_punctuation() -> None:
    assert parse_receipt("TOTAL. 42.98").total == Decimal("42.98")
    assert parse_receipt("TOTAL: 42,98").total == Decimal("42.98")
    assert parse_receipt("TOTAL | 42,98").total == Decimal("42.98")


def test_total_tva_is_still_not_the_total() -> None:
    assert parse_receipt("TOTAL TVA 6,94").total is None


def test_name_line_without_price_uses_the_quantity_line() -> None:
    # The price column was crumpled, but "1,000 BUC x 35,99" is enough.
    lines = parse_receipt("1,000 BUC x 35,99\nNutella Crema cacao alun\nTOTAL 35,99").lines

    assert [(l.raw_text, l.quantity, l.line_total) for l in lines] == [
        ("Nutella Crema cacao alun", Decimal("1.000"), Decimal("35.99")),
    ]


def test_weighed_line_without_price_is_rounded() -> None:
    lines = parse_receipt("0,734 KG x 7,99\nBANANE\nTOTAL 5,86").lines

    assert lines[0].line_total == Decimal("5.86")  # 5.86466 rounded


def test_misread_unit_still_counts_as_a_quantity_line() -> None:
    lines = parse_receipt("1.000 BUD x 9.99\nCocktail fructe suc prop 9,99 B\nTOTAL 9,99").lines

    assert [(l.raw_text, l.quantity) for l in lines] == [("Cocktail fructe suc prop", Decimal("1.000"))]


def test_payment_lines_are_not_items() -> None:
    assert parse_receipt("CASH 100,00\nREST 57,02").lines == []


# --- RapidOCR output from real Lidl receipts --------------------------------


def test_quantity_line_joined_with_a_price_and_dashed_vat_letter() -> None:
    # RapidOCR put the next item's price on the quantity line: "7,99-B".
    lines = parse_receipt("1.000  BUC X 7.99  7,99-B\nChips preparate manual\nTOTAL 7,99").lines

    assert [(l.raw_text, l.quantity, l.line_total) for l in lines] == [
        ("Chips preparate manual", Decimal("1.000"), Decimal("7.99")),
    ]


def test_misread_price_is_dropped_from_the_name() -> None:
    # "6.99 B" read as "6.993", and "35,99 A" as "35:99t".
    text = "1.000  BUC X 6.99\nPaine Durum  6.993\n1,000  BUC X 35.99\nNutella Crema cacao alun  35:99t\nTOTAL 42.98"

    assert [(l.raw_text, l.line_total) for l in parse_receipt(text).lines] == [
        ("Paine Durum", Decimal("6.99")),
        ("Nutella Crema cacao alun", Decimal("35.99")),
    ]


def test_real_lidl_receipt_read_by_rapidocr() -> None:
    text = (FIXTURES / "lidl_rapidocr_1.txt").read_text(encoding="utf-8")

    receipt = parse_receipt(text)

    assert receipt.store_name == "Lidl"
    assert receipt.total == Decimal("25.97")
    assert receipt.purchased_at == datetime(2026, 10, 26)
    assert [(l.raw_text, l.quantity, l.line_total) for l in receipt.lines] == [
        ("Chips preparate manual", Decimal("1.000"), Decimal("7.99")),
        ("cocktail fructe suc prop", Decimal("1.000"), Decimal("9.99")),
        ("Chips preparate manual", Decimal("1.000"), Decimal("7.99")),
    ]


def test_second_real_lidl_receipt_read_by_rapidocr() -> None:
    receipt = parse_receipt((FIXTURES / "lidl_rapidocr_2.txt").read_text(encoding="utf-8"))

    assert (receipt.store_name, receipt.total, receipt.purchased_at) == ("Lidl", Decimal("42.98"), datetime(2026, 10, 16))
    assert [(l.raw_text, l.line_total) for l in receipt.lines] == [
        ("Paine Durum", Decimal("6.99")),
        ("Nutella Crema cacão alun", Decimal("35.99")),
    ]


# --- The receipt's identifier -----------------------------------------------


def test_printed_receipt_code_is_the_identifier() -> None:
    assert parse_receipt("DATA:26/10/2026\nID BF: 8f31a2c9\nBF: 25").identifier == "8F31A2C9"
    assert parse_receipt("COD UNIC 12345678").identifier == "12345678"


def test_receipt_number_is_kept_with_its_z_number() -> None:
    assert parse_receipt("BF: 0025\nZ: 0347").identifier == "Z 0347 / BF 0025"
    assert parse_receipt("Z 0347   BF 0025").identifier == "Z 0347 / BF 0025"


def test_other_ways_of_printing_the_receipt_number() -> None:
    assert parse_receipt("NR. BON: 123").identifier == "BF 123"
    assert parse_receipt("BON FISCAL NR. 123").identifier == "BF 123"


def test_fiscal_code_is_not_the_identifier() -> None:
    text = (FIXTURES / "lidl_rapidocr_1.txt").read_text(encoding="utf-8")

    assert parse_receipt(text).identifier is None


# --- Quantity lines, discounts and times from real phone photos -------------


def fixture_receipt(name: str):
    return parse_receipt((FIXTURES / name).read_text(encoding="utf-8"))


def test_real_multiplication_sign_is_a_quantity_line() -> None:
    lines = parse_receipt("1.000 BUC × 6.49\nFUZETEA 1,5L  6.49 B\nTOTAL 6,49").lines

    assert [(l.raw_text, l.quantity) for l in lines] == [("FUZETEA 1,5L", Decimal("1.000"))]


def test_quantity_line_split_by_the_lei_heading() -> None:
    lines = parse_receipt("1.000  Lei\nBUC X 7.99\nChips  7.99 B\nTOTAL 7,99").lines

    assert [(l.raw_text, l.quantity, l.line_total) for l in lines] == [("Chips", Decimal(1), Decimal("7.99"))]


def test_vat_letter_after_a_dot() -> None:
    lines = parse_receipt("1.000  BUC X 7.99  7.99.B\nChips\nTOTAL 7,99").lines

    assert [(l.raw_text, l.line_total) for l in lines] == [("Chips", Decimal("7.99"))]


def test_discount_lowers_the_product_above_it() -> None:
    text = "CHIPS 14.39 C\nPromotie\nDISCOUNT  4,32-C\nSUC 3.45 B\nTOTAL 13,52"

    assert [(l.raw_text, l.line_total) for l in parse_receipt(text).lines] == [
        ("CHIPS", Decimal("10.07")),
        ("SUC", Decimal("3.45")),
    ]


def test_discount_with_a_leading_minus() -> None:
    lines = parse_receipt("CHIPS 14.39 C\nREDUCERE -4,32\nTOTAL 10,07").lines

    assert [(l.raw_text, l.line_total) for l in lines] == [("CHIPS", Decimal("10.07"))]


def test_discount_before_any_product_is_not_a_product() -> None:
    assert parse_receipt("DISCOUNT 4,32\nTOTAL 0,00").lines == []


def test_time_after_ora_with_dashes() -> None:
    assert parse_receipt("DATA:06/11/2026  ORA:21-36-05").purchased_at == datetime(2026, 11, 6, 21, 36, 5)


def test_misread_time_keeps_the_date() -> None:
    assert parse_receipt("DATA:06/11/2026  ORA:71-36-05").purchased_at == datetime(2026, 11, 6)


def test_price_on_its_own_line_is_not_a_name() -> None:
    for price in ("7.99 B", "7,99-B", "B 7.99", "7.99.B"):
        lines = parse_receipt(f"1.000 BUC X 7.99\n{price}\nChips preparate\nTOTAL 7,99").lines

        assert [(l.raw_text, l.quantity, l.line_total) for l in lines] == [
            ("Chips preparate", Decimal("1.000"), Decimal("7.99")),
        ]


def test_price_after_its_name_is_not_another_product() -> None:
    lines = parse_receipt("1.000 BUC X 7.99\nChips preparate\n7.99 B\nTOTAL 7,99").lines

    assert [l.raw_text for l in lines] == ["Chips preparate"]


def test_printed_price_on_its_own_line_beats_the_computed_one() -> None:
    # The unit price was misread, but the line's own price wasn't.
    lines = parse_receipt("1.000 BUC X 7.89\n7.99 B\nChips preparate\nTOTAL 7,99").lines

    assert lines[0].line_total == Decimal("7.99")


def test_lei_heading_is_not_a_product() -> None:
    lines = parse_receipt("1.000 BUC X 7.99\nLei\nChips preparate  7.99 B\nTOTAL 7,99").lines

    assert [(l.raw_text, l.quantity) for l in lines] == [("Chips preparate", Decimal("1.000"))]


def test_stray_marks_are_not_products() -> None:
    lines = parse_receipt("1.000 BUC X 7.99\n* ?\nab\nChips preparate\nTOTAL 7,99").lines

    assert [l.raw_text for l in lines] == ["Chips preparate"]


def test_short_real_names_stay() -> None:
    assert [l.raw_text for l in parse_receipt("UNT  8,50 A\nTOTAL 8,50").lines] == ["UNT"]


def test_real_kaufland_receipt_with_a_discount_adds_up() -> None:
    receipt = fixture_receipt("kaufland_rapidocr_1.txt")

    assert (receipt.store_name, receipt.total) == ("Kaufland", Decimal("53.66"))
    assert receipt.purchased_at == datetime(2026, 11, 6, 21, 36, 5)
    assert [(l.raw_text, l.quantity, l.line_total) for l in receipt.lines] == [
        ("TRONGBOW CIDRUO,33L", Decimal("1.000"), Decimal("6.49")),
        ("GARANTIE AMBALAJ *", Decimal("1.000"), Decimal("0.50")),
        ("FUZETEA 1,5L", Decimal("1.000"), Decimal("9.09")),
        ("GARANTIE AMBALAJ *", Decimal("1.000"), Decimal("0.50")),
        ("ALFERS NAP. GLAZ180G", Decimal("1.000"), Decimal("9.19")),
        ("CHIO CHIPS 240G", Decimal("1.000"), Decimal("10.07")),
        ("CHIO HULA H0OPS70G", Decimal("2.000"), Decimal("9.58")),
        ("CHIO HULA HOOPS70G", Decimal("1.000"), Decimal("4.79")),
        ("7D CROIS ARAHID 80G", Decimal("1.000"), Decimal("3.45")),
    ]
    assert sum(l.line_total for l in receipt.lines) == receipt.total


ID_UNIC = "60010827022026110612373602640061"
PRINTED = "BF.00061  DATA:06/11/2026  ORA:12-37-36"


def test_a_correct_id_unic_is_kept() -> None:
    assert parse_receipt(f"ID UNIC:{ID_UNIC}\n{PRINTED}").unique_id == ID_UNIC


def test_id_unic_missing_digits_is_rejected() -> None:
    # Read from a real Kaufland photo: OCR lost two zeros.
    receipt = parse_receipt("ID UNIC:300772082026110621360524480289\nBF.00289  DATA:06/11/2026")

    assert receipt.unique_id is None
    assert receipt.identifier == "300772082026110621360524480289"


def test_id_unic_with_another_date_is_rejected() -> None:
    assert parse_receipt(f"ID UNIC:{ID_UNIC}\nBF.00061  DATA:07/11/2026").unique_id is None


def test_id_unic_with_another_receipt_number_is_rejected() -> None:
    assert parse_receipt(f"ID UNIC:{ID_UNIC}\nBF.00062  DATA:06/11/2026").unique_id is None


def test_real_receipts_give_a_checked_id_unic_only_when_read_in_full() -> None:
    assert fixture_receipt("kaufland_rapidocr_1.txt").unique_id is None
    assert fixture_receipt("kaufland_rapidocr_2.txt").unique_id == "70000766432026110621373028760293"
    assert fixture_receipt("kaufland_rapidocr_3.txt").unique_id == ID_UNIC
    assert fixture_receipt("lidl_rapidocr_3.txt").unique_id is None


def test_real_receipt_with_card_discounts_and_every_product() -> None:
    # OCR read this photo's first discount as "0.00-0", so it can't add up, but
    # the second is subtracted, and no discount line became a product.
    receipt = fixture_receipt("kaufland_rapidocr_3.txt")

    assert receipt.total == Decimal("140.39")
    assert len(receipt.lines) == 14
    assert not any("DISCOUNT" in l.raw_text or "XTRA" in l.raw_text for l in receipt.lines)
    assert [l.line_total for l in receipt.lines if l.raw_text == "STAR PURPLE90 G"] == [Decimal("5.79")]


def test_real_single_product_kaufland_receipt() -> None:
    receipt = fixture_receipt("kaufland_rapidocr_2.txt")

    assert [(l.raw_text, l.quantity, l.line_total) for l in receipt.lines] == [
        ("ORBIT SPEARMING 64G", Decimal("1.000"), Decimal("12.99")),
    ]
    assert receipt.total == Decimal("12.99")


def test_real_lidl_photo_has_no_quantity_rows_as_products() -> None:
    receipt = fixture_receipt("lidl_rapidocr_3.txt")

    assert [(l.raw_text, l.line_total) for l in receipt.lines] == [
        ("Chips preparate manual", Decimal("7.99")),
        ("Cocktail fructe suc prop", Decimal("9.99")),
        ("Chips preparate manual", Decimal("7.99")),
    ]
    assert sum(l.line_total for l in receipt.lines) == receipt.total
