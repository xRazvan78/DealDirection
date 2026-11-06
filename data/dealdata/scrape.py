"""Scrape every store once, slowly: `uv run python -m dealdata.scrape`. Owner: Member 1, Task 5.

Raw output goes to data/raw/<date>/, which is never committed. If a site blocks the
scrape, this stops, and the team should be told.

To rebuild data/snapshot/products.json from the newest raw folder, for example after
changing tree.yaml, add --offline. That sends no requests. Without it, a tree change
means new searches, so don't run the plain command just to refresh the snapshot.
"""

import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from pathlib import Path

import httpx

from dealdata.normalize import RawProduct, parse_size
from dealdata.scrape_auchan import read_raw_auchan, scrape_auchan, search_terms
from dealdata.scrape_carrefour import CATEGORY_URLS, read_raw_carrefour, scrape_carrefour
from dealdata.tree import LeafRule, classify, load_tree

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


def build_snapshot(
    products: list[RawProduct], rules: list[LeafRule], scraped_on: date
) -> list[dict]:
    """Describe every product that has a leaf, because store_products requires one."""
    snapshot = []
    for product in products:
        size = parse_size(product.name)
        leaf = classify(product, size, rules) if size else None
        if size and leaf:
            snapshot.append(
                {
                    "store": product.store,
                    "name": product.name,
                    "brand": product.brand,
                    "price": str(product.price),
                    "unit": size.unit,
                    "source_url": product.source_url,
                    "path": [leaf.group, *leaf.path],
                    "updated_at": scraped_on.isoformat(),
                }
            )
    return snapshot


def write_json(path: Path, content: list[dict]) -> None:
    path.write_text(
        json.dumps(content, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def latest_raw_dir() -> Path:
    """Return the newest scrape, as raw folders are named by date."""
    return max(path for path in (DATA_DIR / "raw").iterdir() if path.is_dir())


def main(args: list[str] | None = None) -> int:
    rules = load_tree(DATA_DIR / "tree.yaml")

    if "--offline" in (sys.argv[1:] if args is None else args):
        raw_dir = latest_raw_dir()
        scraped = read_raw_auchan(raw_dir) + read_raw_carrefour(raw_dir)
    else:
        raw_dir = DATA_DIR / "raw" / date.today().isoformat()
        raw_dir.mkdir(parents=True, exist_ok=True)
        client = PoliteClient()
        try:
            scraped = scrape_auchan(client, search_terms(rules), raw_dir)
            scraped += scrape_carrefour(client, CATEGORY_URLS, raw_dir)
        except Blocked as error:
            print(f"Stopped: {error}. Tell the team.", file=sys.stderr)
            return 1

    products = unique_products(scraped)
    write_json(raw_dir / "products.json", [asdict(product) for product in products])

    snapshot = build_snapshot(products, rules, date.fromisoformat(raw_dir.name))
    write_json(DATA_DIR / "snapshot" / "products.json", snapshot)
    print(f"Saved {len(products)} products to {raw_dir}, and {len(snapshot)} to the snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
