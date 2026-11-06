"""Supermarket brands a loyalty card can belong to.

Kept apart from the price-comparison stores: a client can keep a Lidl or
Kaufland card even though those shops aren't compared. Colours are close to
each brand's own and only used to draw the card.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Brand:
    id: str
    name: str
    colour: str
    keywords: tuple[str, ...]  # folded words that name the brand on a card or in its code


BRANDS: tuple[Brand, ...] = (
    Brand("lidl", "Lidl", "#0050aa", ("lidl",)),
    Brand("kaufland", "Kaufland", "#e10915", ("kaufland",)),
    Brand("auchan", "Auchan", "#d6001c", ("auchan",)),
    Brand("carrefour", "Carrefour", "#004e9f", ("carrefour",)),
    Brand("mega-image", "Mega Image", "#e30613", ("mega image", "megaimage")),
    Brand("profi", "Profi", "#f39200", ("profi",)),
    Brand("penny", "Penny", "#cd1414", ("penny",)),
)

_BY_ID = {brand.id: brand for brand in BRANDS}


def brand_by_id(brand_id: str) -> Brand | None:
    return _BY_ID.get(brand_id)
