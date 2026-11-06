"""parse_carrefour() and the Carrefour category pages. Owner: Member 1, Task 5.

Only product names, prices and links are kept. Carrefour's data-name and data-brand
attributes can describe a different product, so names come from the title link.
Its search and ajax paths are disallowed, so this only reads category pages.
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from dealdata.normalize import RawProduct

_BASE = "https://carrefour.ro"
_GROCERY = f"{_BASE}/bacanie-carrefour"
_CLEANING = f"{_BASE}/casa-gradina-si-petshop/produse-curatenie-pentru-casa"

CATEGORY_URLS = [
    f"{_GROCERY}/alimente/lapte-si-derivate-lapte-uht/",
    f"{_GROCERY}/alimente/paine-si-specialitati/",
    f"{_GROCERY}/alimente/fainuri/",
    f"{_GROCERY}/alimente/zahar-si-ingrediente-prajituri/",
    f"{_GROCERY}/alimente/condimente-si-sare/",
    f"{_GROCERY}/alimente/orez-si-legume-uscate/",
    f"{_GROCERY}/alimente/paste-fainoase/",
    f"{_GROCERY}/alimente/ulei/",
    f"{_GROCERY}/alimente/otet/",
    f"{_GROCERY}/alimente/conserve/",
    f"{_GROCERY}/alimente/cafea/",
    f"{_GROCERY}/alimente/ceai/",
    f"{_GROCERY}/alimente/ciocolata/",
    f"{_GROCERY}/bauturi-nealcoolice/apa/",
    f"{_GROCERY}/bauturi-nealcoolice/sucuri-si-nectaruri/",
    f"{_CLEANING}/intretinere-rufe/detergent-pentru-rufe/",
    f"{_CLEANING}/detergenti-vase/detergent-manual-vase/",
    f"{_CLEANING}/servetele-si-produse-din-hartie/hartie-igienica/",
]

MAX_PAGES = 3


def parse_carrefour(html: str, source_url: str) -> list[RawProduct]:
    """Turn a category page into products, skipping any with no name or price."""
    products = []
    for item in BeautifulSoup(html, "html.parser").select("li.product"):
        link = item.select_one(".productItem-name a")
        price = item.select_one("[data-price-amount]")
        if link is None or price is None:
            continue
        products.append(
            RawProduct(
                store="Carrefour",
                name=str(link.get("title") or link.get_text(strip=True)),
                brand=None,
                barcode=None,
                price=Decimal(str(price["data-price-amount"]).replace(",", ".")),
                image_url=None,
                source_url=str(link.get("href") or source_url),
            )
        )
    return products


def scrape_carrefour(
    client: Any, urls: list[str], raw_dir: Path, max_pages: int = MAX_PAGES
) -> list[RawProduct]:
    """Read each category's pages, saving the raw page before parsing it.

    A page already saved in raw_dir is reused, so a re-run only fetches what's missing.
    """
    products = []
    for index, url in enumerate(urls):
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            page_url = url if page == 1 else f"{url}?p={page}"
            raw_file = raw_dir / f"carrefour_{index:03}_p{page}.html"
            if not raw_file.exists():
                raw_file.write_text(client.get(page_url).text, encoding="utf-8")
            html = raw_file.read_text(encoding="utf-8")

            new = [p for p in parse_carrefour(html, page_url) if p.source_url not in seen]
            if not new:
                break
            seen.update(product.source_url for product in new)
            products += new
    return products
