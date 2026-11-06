"""Pure points calculation: no database or HTTP. Owner: Member 3, Task 2.

The rule is in the README under "Receipts and points":
paying 5% or more above the estimate raises the points, up to a cap.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class PointsResult:
    estimate: Decimal
    paid: Decimal
    diff: Decimal  # (paid - estimate) / estimate, so 0.12 means 12% over
    modifier: Decimal
    points: int


def calculate_points(
    estimate: Decimal,
    paid: Decimal,
    margin: Decimal,
    max_modifier: Decimal,
    points_per_lei: int,
) -> PointsResult:
    """Points for the matched items on one receipt.

    Pass the config values (MARGIN, MAX_MODIFIER, POINTS_PER_LEI) in, so this
    stays testable without settings.
    """
    if estimate <= 0:
        raise ValueError("estimate must be greater than zero")

    diff = (paid - estimate) / estimate
    modifier = Decimal("1.00") if diff < margin else min(1 + diff, max_modifier)

    raw = estimate * points_per_lei * modifier
    points = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    return PointsResult(
        estimate=estimate,
        paid=paid,
        diff=diff,
        modifier=modifier,
        points=points,
    )
