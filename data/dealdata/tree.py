"""LeafRule, load_tree() and classify(). Owner: Member 1, Task 4."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from dealdata.normalize import Size, parse_size


@dataclass(frozen=True)
class LeafRule:
    path: tuple[str, str, str]
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    size: Size
    aliases: tuple[str, ...]


def load_tree(path: Path) -> list[LeafRule]:
    """Read tree.yaml, and return one rule per size-level leaf."""
    tree = yaml.safe_load(path.read_text(encoding="utf-8"))

    rules = []
    for category in tree["categories"]:
        for product_type in category["types"]:
            for size_text in product_type["sizes"]:
                size = parse_size(size_text)
                if size is None:
                    raise ValueError(f"Unreadable size in {path}: {size_text!r}")
                rules.append(
                    LeafRule(
                        path=(category["name"], product_type["name"], size_text),
                        include=tuple(product_type["include"]),
                        exclude=tuple(product_type.get("exclude", ())),
                        size=size,
                        aliases=tuple(product_type.get("aliases", ())),
                    )
                )
    return rules
