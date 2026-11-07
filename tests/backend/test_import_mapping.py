"""Task 12: scale_foods(), packs_needed() and choose_size(). Pure logic."""

from decimal import Decimal

from app.documents.schemas import Food, FoodList
from app.imports.mapping import ScaledFood, Size, choose_size, packs_needed, scale_foods


def food(name: str, amount: str, unit: str, per_day: bool = False) -> Food:
    return Food(name=name, amount=Decimal(amount), unit=unit, per_day=per_day)


def scaled(foods: list[Food], days: int, plan_days: int | None = None) -> list[tuple[str, Decimal, str]]:
    return [(f.name, f.amount, f.unit) for f in scale_foods(FoodList(plan_days=plan_days, foods=foods), days)]


# --- scale_foods ------------------------------------------------------------


def test_daily_food_is_multiplied_by_days_and_converted() -> None:
    assert scaled([food("piept de pui", "200", "g", per_day=True)], 7) == [("piept de pui", Decimal("1.4"), "kg")]


def test_millilitres_become_litres() -> None:
    assert scaled([food("lapte", "250", "ml", per_day=True)], 4) == [("lapte", Decimal("1"), "l")]


def test_plan_over_more_days_is_scaled_up() -> None:
    # A 7-day plan bought for 14 days doubles.
    assert scaled([food("orez", "500", "g")], 14, plan_days=7) == [("orez", Decimal("1"), "kg")]


def test_plain_list_without_plan_days_stays_as_written() -> None:
    assert scaled([food("mere", "1", "kg")], 1) == [("mere", Decimal("1"), "kg")]
    assert scaled([food("mere", "1", "kg")], 5) == [("mere", Decimal("1"), "kg")]


def test_pieces_stay_pieces() -> None:
    assert scaled([food("oua", "2", "buc", per_day=True)], 7) == [("oua", Decimal("14"), "buc")]


def test_repeated_foods_are_added_up() -> None:
    foods = [food("Orez", "100", "g", per_day=True), food("lapte", "1", "l"), food("orez ", "300", "g")]

    assert scaled(foods, 2) == [("Orez", Decimal("0.5"), "kg"), ("lapte", Decimal("1"), "l")]


def test_same_food_in_different_units_stays_apart() -> None:
    assert len(scale_foods(FoodList(plan_days=None, foods=[food("oua", "6", "buc"), food("oua", "300", "g")]), 1)) == 2


def test_scaled_food_is_a_frozen_value() -> None:
    assert scale_foods(FoodList(plan_days=None, foods=[food("mere", "1", "kg")]), 1) == [ScaledFood("mere", Decimal("1"), "kg")]


# --- packs_needed -----------------------------------------------------------


def test_packs_round_up() -> None:
    assert packs_needed(Decimal("1.4"), "kg", Decimal("1"), "kg") == 2


def test_exact_amount_needs_no_extra_pack() -> None:
    assert packs_needed(Decimal("2"), "l", Decimal("1"), "l") == 2


def test_grams_against_kilograms() -> None:
    assert packs_needed(Decimal("750"), "g", Decimal("0.5"), "kg") == 2


def test_incompatible_units_give_none() -> None:
    assert packs_needed(Decimal("1"), "kg", Decimal("1"), "l") is None
    assert packs_needed(Decimal("6"), "buc", Decimal("1"), "kg") is None


def test_empty_pack_size_gives_none() -> None:
    assert packs_needed(Decimal("1"), "kg", Decimal("0"), "kg") is None


# --- choose_size ------------------------------------------------------------

RICE = [Size(1, Decimal("0.1"), "kg"), Size(2, Decimal("0.5"), "kg"), Size(3, Decimal("1"), "kg")]


def test_choose_size_balances_waste_and_pack_count() -> None:
    # 14 x 100 g wastes nothing but is absurd; 2 x 1 kg wastes 600 g; 3 x 500 g is best.
    assert choose_size(Decimal("1.4"), "kg", RICE) == (2, 3)


def test_one_pack_that_fits_wins() -> None:
    assert choose_size(Decimal("0.9"), "kg", RICE) == (3, 1)


def test_a_huge_pack_is_not_chosen_for_a_small_amount() -> None:
    sizes = [Size(1, Decimal("0.5"), "kg"), Size(2, Decimal("10"), "kg")]

    assert choose_size(Decimal("0.4"), "kg", sizes) == (1, 1)


def test_only_compatible_units_are_considered() -> None:
    coffee = [Size(1, Decimal("0.5"), "kg"), Size(2, Decimal("36"), "buc")]

    assert choose_size(Decimal("30"), "buc", coffee) == (2, 1)
    assert choose_size(Decimal("1"), "l", coffee) is None


def test_ties_go_to_the_first_size() -> None:
    assert choose_size(Decimal("1"), "kg", [Size(5, Decimal("1"), "kg"), Size(4, Decimal("1"), "kg")]) == (5, 1)
