"""Scrape every store once, slowly: `uv run python -m dealdata.scrape`. Owner: Member 1, Task 5.

Raw output goes to data/raw/<date>/, which is never committed. If a site blocks the
scrape, this stops, and the team should be told.
"""

import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from pathlib import Path

import httpx

from dealdata.normalize import RawProduct
from dealdata.scrape_auchan import scrape_auchan, search_terms
from dealdata.scrape_carrefour import CATEGORY_URLS, scrape_carrefour
from dealdata.tree import load_tree

USER_AGENT = "DealDirection/0.1"
MIN_SECONDS_BETWEEN_REQUESTS = 1.0

DATA_DIR = Path(__file__).parents[1]


class Blocked(Exception):
    """A site refused a request or failed, so scraping must stop."""


class PoliteClient:
    """HTTP client that keeps to the request limit, and stops at the first error."""

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            transport=transport,
            timeout=30,
            follow_redirects=True,
        )
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        if self._last_request is not None:
            wait = MIN_SECONDS_BETWEEN_REQUESTS - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)

        try:
            response = self._client.get(url, params=params)
        except httpx.HTTPError as error:
            raise Blocked(f"{url}: {error}") from error
        self._last_request = self._clock()

        if not response.is_success:
            raise Blocked(f"{response.status_code} from {url}")
        return response


def unique_products(products: list[RawProduct]) -> list[RawProduct]:
    """Keep the first product for each store and name."""
    unique: dict[tuple[str, str], RawProduct] = {}
    for product in products:
        unique.setdefault((product.store, product.name), product)
    return list(unique.values())


def main() -> int:
    raw_dir = DATA_DIR / "raw" / date.today().isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)
    rules = load_tree(DATA_DIR / "tree.yaml")
    client = PoliteClient()

    try:
        auchan = scrape_auchan(client, search_terms(rules), raw_dir)
        carrefour = scrape_carrefour(client, CATEGORY_URLS, raw_dir)
    except Blocked as error:
        print(f"Stopped: {error}. Tell the team.", file=sys.stderr)
        return 1

    products = unique_products(auchan + carrefour)
    (raw_dir / "products.json").write_text(
        json.dumps([asdict(product) for product in products], default=str, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(products)} products to {raw_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
