"""Task 2: points calculation. Values come from the TEAM_TASKS table."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.points.logic import PointsResult, calculate_points

MARGIN = Decimal("0.05")
MAX_MODIFIER = Decimal("1.25")
POINTS_PER_LEI = 10


def calc(estimate: str, paid: str) -> PointsResult:
    return calculate_points(
        estimate=Decimal(estimate),
        paid=Decimal(paid),
        margin=MARGIN,
        max_modifier=MAX_MODIFIER,
        points_per_lei=POINTS_PER_LEI,
    )


@pytest.mark.parametrize(
    ("paid", "modifier", "points"),
    [
        ("90", "1.00", 1000),  # paid less: full points
        ("103", "1.00", 1000),  # under 5% more: full points
        ("105", "1.05", 1050),  # exactly 5% more: the bonus starts
        ("112", "1.12", 1120),  # 12% more gives x1.12
        ("140", "1.25", 1250),  # capped at the maximum
    ],
)
def test_points_table(paid: str, modifier: str, points: int) -> None:
    result = calc("100", paid)

    assert result.modifier == Decimal(modifier)
    assert result.points == points


def test_result_keeps_inputs_and_difference() -> None:
    result = calc("100", "112")

    assert result.estimate == Decimal("100")
    assert result.paid == Decimal("112")
    assert result.diff == Decimal("0.12")


def test_points_are_an_int() -> None:
    assert isinstance(calc("100", "112").points, int)


def test_points_round_half_up() -> None:
    # 0.05 lei x 10 = 0.5 points. Python's round() would give 0.
    assert calc("0.05", "0.05").points == 1


def test_zero_estimate_raises() -> None:
    with pytest.raises(ValueError):
        calc("0", "10")


def test_negative_estimate_raises() -> None:
    with pytest.raises(ValueError):
        calc("-5", "10")


def test_result_is_frozen() -> None:
    result = calc("100", "100")

    with pytest.raises(FrozenInstanceError):
        result.points = 5  # type: ignore[misc]
