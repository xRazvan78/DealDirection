"""The demo shopping list must show a real split on stage. Owner: Member 1, Task 19.

These read the real snapshot, so a new scrape that spoils the demo fails here first.
"""

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.config import get_settings

DATA = Path(__file__).resolve().parents[2] / "data"
STORES = ("Auchan", "Carrefour")


def _items() -> list[dict[str, Any]]:
    return yaml.safe_load((DATA / "demo_list.yaml").read_text(encoding="utf-8"))["items"]


def _offers() -> dict[tuple[str, ...], dict[str, list[dict[str, Any]]]]:
    products = json.loads((DATA / "snapshot" / "products.json").read_text(encoding="utf-8"))
    offers: dict[tuple[str, ...], dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for product in products:
        offers[tuple(product["path"])][product["store"]].append(product)
    return offers


def _lowest(offers: list[dict[str, Any]]) -> Decimal:
    return min(Decimal(offer["price"]) for offer in offers)


def _line_totals() -> list[dict[str, Decimal]]:
    """Each item's cost per store, using Task 3's rule of the cheapest offer in its leaf."""
    offers = _offers()
    return [
        {
            store: _lowest(offers[tuple(item["path"])][store]) * item["quantity"]
            for store in STORES
        }
        for item in _items()
    ]


@pytest.mark.parametrize("store", STORES)
def test_each_item_is_sold_at_the_store(store: str) -> None:
    offers = _offers()
    missing = [item["path"] for item in _items() if not offers[tuple(item["path"])][store]]
    assert missing == []


@pytest.mark.parametrize("store", STORES)
def test_the_named_product_is_what_the_optimiser_would_pick(store: str) -> None:
    """A misplaced or cheaper product in the leaf would change what the plan shows."""
    offers = _offers()
    for item in _items():
        leaf = offers[tuple(item["path"])][store]
        named = [offer for offer in leaf if offer["name"] == item[store.lower()]]
        assert named, f"{item[store.lower()]} isn't in {item['path']}"
        assert Decimal(named[0]["price"]) == _lowest(leaf), item[store.lower()]


def test_no_item_costs_the_same_at_both_stores() -> None:
    """A tie would leave the split's store, and so the receipt to buy, unclear."""
    assert all(line["Auchan"] != line["Carrefour"] for line in _line_totals())


def test_the_split_buys_from_both_stores() -> None:
    lines = _line_totals()
    assert any(line["Auchan"] < line["Carrefour"] for line in lines)
    assert any(line["Carrefour"] < line["Auchan"] for line in lines)


def test_the_split_saving_clears_the_threshold() -> None:
    lines = _line_totals()
    best_single = min(sum(line[store] for line in lines) for store in STORES)
    split = sum(min(line.values()) for line in lines)
    assert best_single - split >= get_settings().MIN_SPLIT_SAVING_LEI
