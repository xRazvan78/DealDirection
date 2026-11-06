"""parse_auchan() and the Auchan catalog search. Owner: Member 1, Task 5.

Only product names, brands, prices and links are kept.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

from dealdata.normalize import RawProduct
from dealdata.tree import LeafRule

SEARCH_URL = "https://www.auchan.ro/api/catalog_system/pub/products/search"
PAGE_SIZE = 50


def parse_auchan(payload: list[dict]) -> list[RawProduct]:
    """Turn a catalog response into products, skipping any that are out of stock."""
    products = []
    for item in payload:
        offer = _first_offer(item)
        if offer is None or offer["AvailableQuantity"] <= 0:
            continue
        products.append(
            RawProduct(
                store="Auchan",
                name=item["productName"],
                brand=item.get("brand"),
                barcode=None,
                # str() first, so the float 8.49 stays exactly 8.49.
                price=Decimal(str(offer["Price"])),
                image_url=None,
                source_url=item["link"],
            )
        )
    return products


def _first_offer(item: dict) -> dict | None:
    try:
        return item["items"][0]["sellers"][0]["commertialOffer"]
    except (KeyError, IndexError):
        return None


def search_terms(rules: list[LeafRule]) -> list[str]:
    """Return one search for each type in the tree, in tree order."""
    terms = (" ".join(rule.include or rule.any_of[:1]) for rule in rules)
    return list(dict.fromkeys(term for term in terms if term))


def read_raw_auchan(raw_dir: Path) -> list[RawProduct]:
    """Parse responses already saved in raw_dir, without sending any request."""
    products = []
    for raw_file in sorted(raw_dir.glob("auchan_*.json")):
        products += parse_auchan(json.loads(raw_file.read_text(encoding="utf-8")))
    return products


def scrape_auchan(client: Any, terms: list[str], raw_dir: Path) -> list[RawProduct]:
    """Run each search, saving the raw response before parsing it.

    A response already saved in raw_dir is reused, so a re-run only fetches what's missing.
    """
    products = []
    for index, term in enumerate(terms):
        raw_file = raw_dir / f"auchan_{index:03}.json"
        if not raw_file.exists():
            # quote() sends a space as %20, because Auchan answers 400 to the "+" form.
            url = f"{SEARCH_URL}?ft={quote(term)}&_from=0&_to={PAGE_SIZE - 1}"
            raw_file.write_text(client.get(url).text, encoding="utf-8")
        products += parse_auchan(json.loads(raw_file.read_text(encoding="utf-8")))
    return products
