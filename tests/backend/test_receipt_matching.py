"""Task 11: fingerprint() and score_matches(). Pure logic, no database."""

from datetime import datetime
from decimal import Decimal

from app.documents.schemas import LineMatch, ReceiptLine
from app.receipts.matching import MatchedLine, fingerprint, score_matches


def line(text: str, total: str, qty: str = "1") -> ReceiptLine:
    return ReceiptLine(raw_text=text, quantity=Decimal(qty), line_total=Decimal(total))


def item(item_id: int, qty: str, price: str) -> dict:
    return {"id": item_id, "quantity": Decimal(qty), "estimated_price": Decimal(price)}


# --- fingerprint ------------------------------------------------------------


def test_fingerprint_is_a_sha256_hex() -> None:
    value = fingerprint(1, datetime(2026, 10, 26, 11, 39), Decimal("25.97"))

    assert len(value) == 64
    assert int(value, 16) >= 0


def test_same_receipt_gives_the_same_fingerprint() -> None:
    first = fingerprint(1, datetime(2026, 10, 26), Decimal("25.97"))

    assert fingerprint(1, datetime(2026, 10, 26), Decimal("25.970")) == first


def test_time_of_day_is_ignored() -> None:
    # OCR reads the time on one scan and misses it on the next; a rescan of
    # the same paper must still count as the same receipt.
    assert fingerprint(1, datetime(2026, 10, 26, 11, 39), Decimal("25.97")) == fingerprint(
        1, datetime(2026, 10, 26), Decimal("25.97")
    )


def test_store_date_or_total_change_the_fingerprint() -> None:
    base = fingerprint(1, datetime(2026, 10, 26), Decimal("25.97"))

    assert fingerprint(2, datetime(2026, 10, 26), Decimal("25.97")) != base
    assert fingerprint(1, datetime(2026, 10, 27), Decimal("25.97")) != base
    assert fingerprint(1, datetime(2026, 10, 26), Decimal("25.98")) != base


# --- score_matches ----------------------------------------------------------


def test_weighed_item_counts_what_was_bought() -> None:
    # 1 kg listed at 10 lei/kg, 0.734 kg bought for 7.34 lei.
    estimate, paid, matched = score_matches(
        [LineMatch(line_index=0, item_id=7)], [line("BANANE", "7.34", "0.734")], [item(7, "1", "10")]
    )

    assert (estimate, paid) == (Decimal("7.34"), Decimal("7.34"))
    assert matched == [
        MatchedLine(line_index=0, item_id=7, quantity=Decimal("0.734"), estimate=Decimal("7.34"), paid=Decimal("7.34"))
    ]


def test_extra_packs_bought_only_count_up_to_the_list() -> None:
    # 1 pack listed, 5 packs bought at 5 lei each.
    estimate, paid, _ = score_matches(
        [LineMatch(line_index=0, item_id=7)], [line("PAINE", "25.00", "5")], [item(7, "1", "5")]
    )

    assert (estimate, paid) == (Decimal("5.00"), Decimal("5.00"))


def test_paying_more_shows_in_paid_not_estimate() -> None:
    estimate, paid, _ = score_matches(
        [LineMatch(line_index=0, item_id=1), LineMatch(line_index=1, item_id=2)],
        [line("LAPTE", "11.20"), line("PAINE", "5.60", "2")],
        [item(1, "1", "10"), item(2, "2", "2.50")],
    )

    assert (estimate, paid) == (Decimal("15.00"), Decimal("16.80"))


def test_unknown_items_lines_and_repeats_are_ignored() -> None:
    matches = [
        LineMatch(line_index=0, item_id=1),
        LineMatch(line_index=0, item_id=2),  # line 0 used twice
        LineMatch(line_index=1, item_id=1),  # item 1 used twice
        LineMatch(line_index=1, item_id=99),  # not on this list part
        LineMatch(line_index=9, item_id=2),  # no such line
    ]

    estimate, paid, matched = score_matches(matches, [line("A", "10"), line("B", "3")], [item(1, "1", "10"), item(2, "1", "3")])

    assert [(m.line_index, m.item_id) for m in matched] == [(0, 1)]
    assert (estimate, paid) == (Decimal("10.00"), Decimal("10.00"))


def test_zero_quantity_line_is_ignored() -> None:
    estimate, paid, matched = score_matches(
        [LineMatch(line_index=0, item_id=1)], [line("A", "0", "0")], [item(1, "1", "10")]
    )

    assert (estimate, paid, matched) == (Decimal("0"), Decimal("0"), [])


def test_no_matches_gives_zero() -> None:
    assert score_matches([], [line("A", "1")], [item(1, "1", "1")]) == (Decimal("0"), Decimal("0"), [])


# --- merge_repeated_lines ---------------------------------------------------

from app.receipts.matching import merge_repeated_lines  # noqa: E402


def test_repeated_lines_are_merged() -> None:
    # Two bags scanned separately at the till print as two lines.
    merged = merge_repeated_lines(
        [line("Chips preparate manual", "7.99"), line("Cocktail fructe", "9.99"), line("chips  preparate manual", "7.99")]
    )

    assert [(l.raw_text, l.quantity, l.line_total) for l in merged] == [
        ("Chips preparate manual", Decimal("2"), Decimal("15.98")),
        ("Cocktail fructe", Decimal("1"), Decimal("9.99")),
    ]


def test_merged_lines_count_for_a_bigger_list_quantity() -> None:
    lines = merge_repeated_lines([line("CHIPS", "7.99"), line("CHIPS", "7.99")])

    estimate, paid, _ = score_matches([LineMatch(line_index=0, item_id=1)], lines, [item(1, "2", "7.99")])

    assert (estimate, paid) == (Decimal("15.98"), Decimal("15.98"))


def test_different_lines_stay_apart() -> None:
    assert len(merge_repeated_lines([line("LAPTE 1L", "7.99"), line("LAPTE 2L", "12.99")])) == 2
