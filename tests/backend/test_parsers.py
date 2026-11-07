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

import pytest  # noqa: E402

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


# --- Counts without a unit --------------------------------------------------


def test_count_without_a_unit_means_pieces() -> None:
    food = only_food("2 oua zilnic")

    assert (food.name, food.amount, food.unit, food.per_day) == ("oua", Decimal("2"), "buc", True)


def test_count_after_a_meal_label() -> None:
    foods = parse_foods("Mic dejun: 2 oua zilnic, 250 ml lapte zilnic").foods

    assert [(f.name, f.amount, f.unit) for f in foods] == [("oua", Decimal("2"), "buc"), ("lapte", Decimal("250"), "ml")]


def test_plan_length_and_day_numbers_are_not_foods() -> None:
    assert parse_foods("Plan 7 zile\nZiua 1\n3 mese pe zi\nMasa 2: 1 banana").foods == [
        parse_foods("1 banana").foods[0]
    ]


# --- Real receipts photographed on a phone (RapidOCR text) -------------------


def items(receipt) -> list[tuple[str, Decimal, Decimal]]:
    return [(l.raw_text, l.quantity, l.line_total) for l in receipt.lines]


def test_kaufland_receipt_with_multiplication_signs_discount_and_deposits() -> None:
    receipt = parse_receipt((FIXTURES / "kaufland_rapidocr_1.txt").read_text(encoding="utf-8"))

    assert receipt.store_name == "Kaufland"
    assert items(receipt) == [
        ("TRONGBOW CIDRUO,33L", Decimal("1.000"), Decimal("6.49")),
        ("FUZETEA 1,5L", Decimal("1.000"), Decimal("9.09")),
        ("ALFERS NAP. GLAZ180G", Decimal("1.000"), Decimal("9.19")),
        ("CHIO CHIPS 240G", Decimal("1.000"), Decimal("10.07")),  # 14.39 minus the 4.32 discount
        ("CHIO HULA H0OPS70G", Decimal("2.000"), Decimal("9.58")),
        ("CHIO HULA HOOPS70G", Decimal("1.000"), Decimal("4.79")),
        ("7D CROIS ARAHID 80G", Decimal("1.000"), Decimal("3.45")),
    ]
    assert receipt.deposits == Decimal("1.00")  # two 0.50 bottle deposits, not products
    assert receipt.total == Decimal("53.66")
    assert receipt.adds_up is True
    assert receipt.purchased_at == datetime(2026, 11, 6, 21, 36, 5)


def test_kaufland_ids_when_the_id_unic_lost_digits() -> None:
    receipt = parse_receipt((FIXTURES / "kaufland_rapidocr_1.txt").read_text(encoding="utf-8"))

    # OCR dropped two zeros from the 32-digit ID, so it's kept as read but not trusted;
    # the register (RL), time (ORA) and receipt number (BF) are read on their own.
    assert receipt.receipt_id == "300772082026110621360524480289"
    assert (receipt.register_id, receipt.receipt_number) == ("3000077208", "289")
    assert receipt.fiscal_key == "3000077208|20261106|2136|289"


def test_second_kaufland_receipt() -> None:
    receipt = parse_receipt((FIXTURES / "kaufland_rapidocr_2.txt").read_text(encoding="utf-8"))

    assert items(receipt) == [("ORBIT SPEARMING 64G", Decimal("1.000"), Decimal("12.99"))]
    assert receipt.adds_up is True
    # "ORA:21-37-3" lost a seconds digit: the time is kept to the minute.
    assert receipt.purchased_at == datetime(2026, 11, 6, 21, 37)
    # No number after "RL": the register comes from the start of the ID UNIC.
    assert receipt.receipt_id == "70000766432026110621373028760293"
    assert receipt.fiscal_key == "7000076643|20261106|2137|293"


def test_lidl_receipt_with_a_dot_before_the_vat_letter() -> None:
    receipt = parse_receipt((FIXTURES / "lidl_rapidocr_3.txt").read_text(encoding="utf-8"))

    assert items(receipt) == [
        ("Chips preparate manual", Decimal("1.000"), Decimal("7.99")),
        ("cocktail fructe suc prop", Decimal("1.000"), Decimal("9.99")),
        ("Chips preparate manual", Decimal("1.000"), Decimal("7.99")),  # "7,99.B" was lost before
    ]
    assert (receipt.total, receipt.adds_up) == (Decimal("25.97"), True)


def test_lidl_ids_when_the_id_unic_is_cut_off() -> None:
    receipt = parse_receipt((FIXTURES / "lidl_rapidocr_3.txt").read_text(encoding="utf-8"))

    # The photo cut the ID short, but its start still lines up with the date,
    # so the register and the time (no ORA was read) come from it.
    assert receipt.purchased_at == datetime(2026, 10, 26, 11, 39, 10)
    assert receipt.fiscal_key == "8000700393|20261026|1139|240"


# --- The individual fixes ---------------------------------------------------


def test_multiplication_sign_quantity_line() -> None:
    assert items(parse_receipt("2.000 BUC × 4.79\nCHIO HULA HOOPS 9.58 C\nTOTAL 9.58")) == [
        ("CHIO HULA HOOPS", Decimal("2.000"), Decimal("9.58"))
    ]


@pytest.mark.parametrize("price", ["7,99 B", "7,99B", "7,99-B", "7,99.B", "7.99 b"])
def test_vat_letter_after_any_separator(price: str) -> None:
    assert items(parse_receipt(f"1.000 BUC X 7.99\nCHIPS {price}\nTOTAL 7.99")) == [
        ("CHIPS", Decimal("1.000"), Decimal("7.99"))
    ]


def test_discount_is_taken_off_the_product_above() -> None:
    text = "1.000 BUC X 10.00\nCAFEA 10.00 B\nPromotie\nDISCOUNT 2,50-B\nTOTAL 7.50"

    assert items(parse_receipt(text)) == [("CAFEA", Decimal("1.000"), Decimal("7.50"))]


def test_discount_never_makes_a_price_negative() -> None:
    assert items(parse_receipt("CAFEA 1.00 B\nREDUCERE 5.00-B\nTOTAL 0.00"))[0][2] == Decimal("0.00")


def test_discount_before_any_product_is_ignored() -> None:
    assert items(parse_receipt("DISCOUNT 1.00-B\nCAFEA 5.00 B\nTOTAL 5.00")) == [("CAFEA", Decimal("1"), Decimal("5.00"))]


@pytest.mark.parametrize("name", ["GARANTIE AMBALAJ *", "RANTIE AMBALAJ *", "Garantie SGR", "AMBALAJ SGR"])
def test_bottle_deposits_are_not_products(name: str) -> None:
    receipt = parse_receipt(f"1.000 BUC X 0.50\n{name} 0.50 D\nAPA 2L 3.00 B\nTOTAL 3.50")

    assert [l.raw_text for l in receipt.lines] == ["APA 2L"]
    assert receipt.deposits == Decimal("0.50")
    assert receipt.adds_up is True


def test_lines_that_dont_add_up_are_flagged() -> None:
    receipt = parse_receipt("CAFEA 10.00 B\nTOTAL 15.00")  # a product line was missed

    assert receipt.adds_up is False


def test_adds_up_is_unknown_without_a_total() -> None:
    assert parse_receipt("CAFEA 10.00 B").adds_up is None


def test_time_from_ora() -> None:
    assert parse_receipt("DATA:06/11/2026 ORA:21-36-05").purchased_at == datetime(2026, 11, 6, 21, 36, 5)
    assert parse_receipt("DATA: 06.11.2026  ORA: 09:15").purchased_at == datetime(2026, 11, 6, 9, 15)


def test_consistent_id_unic_gives_every_piece() -> None:
    receipt = parse_receipt("ID UNIC: 30000772082026110621360524480289\nDATA:06/11/2026")

    assert (receipt.register_id, receipt.receipt_number) == ("3000077208", "289")
    assert receipt.purchased_at == datetime(2026, 11, 6, 21, 36, 5)
    assert receipt.fiscal_key == "3000077208|20261106|2136|289"


def test_id_unic_with_spaces_is_joined() -> None:
    assert parse_receipt("ID UNIC: 3000077208 2026110621 3605244802 89").receipt_id == "30000772082026110621360524480289"


def test_no_fiscal_key_without_enough_pieces() -> None:
    receipt = parse_receipt("KAUFLAND\nCAFEA 10.00 B\nTOTAL 10.00\nDATA:06/11/2026")

    assert (receipt.receipt_id, receipt.register_id, receipt.receipt_number, receipt.fiscal_key) == (None, None, None, None)


def test_dash_after_a_price_with_a_quantity_line_is_a_product() -> None:
    # OCR read "7,99 B" as "7,99-B": the quantity line above shows it's a product.
    assert items(parse_receipt("1.000 BUC X 7.99\nCHIPS 7,99-B\nTOTAL 7.99")) == [("CHIPS", Decimal("1.000"), Decimal("7.99"))]
