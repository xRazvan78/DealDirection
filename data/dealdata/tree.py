"""LeafRule, load_tree() and classify(). Owner: Member 1, Task 4."""

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml
from app.textutil import fold

from dealdata.normalize import RawProduct, Size, parse_size


@dataclass(frozen=True)
class LeafRule:
    path: tuple[str, str, str]
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    size: Size
    aliases: tuple[str, ...]
    group: str = ""
    any_of: tuple[str, ...] = ()
    starts_with: tuple[str, ...] = ()


@dataclass(frozen=True)
class CategoryNode:
    """One row of the categories table, identified by its names from the top down."""

    path: tuple[str, ...]
    level: str
    size_amount: Decimal | None = None
    size_unit: str | None = None
    aliases: tuple[str, ...] = ()

    @property
    def parent(self) -> tuple[str, ...] | None:
        return self.path[:-1] or None


def category_nodes(rules: list[LeafRule]) -> list[CategoryNode]:
    """Turn leaves into categories rows, with each parent before its children.

    The table's levels are category, type and size, so a big group is simply a
    `category` row with no parent, and its categories are `category` rows under it.
    """
    nodes: dict[tuple[str, ...], CategoryNode] = {}
    for rule in rules:
        group = (rule.group,) if rule.group else ()
        category, type_name, size_text = rule.path
        for path, level in (
            (group, "category"),
            ((*group, category), "category"),
            ((*group, category, type_name), "type"),
        ):
            if path:
                nodes.setdefault(path, CategoryNode(path, level))
        leaf = (*group, category, type_name, size_text)
        nodes[leaf] = CategoryNode(leaf, "size", rule.size.amount, rule.size.unit, rule.aliases)
    return list(nodes.values())


def classify(product: RawProduct, size: Size, rules: list[LeafRule]) -> LeafRule | None:
    """Return the first leaf that fits, so the order of tree.yaml matters."""
    text = _comparable(product.name)
    for rule in rules:
        if rule.size == size and _fits(rule, text):
            return rule
    return None


def _comparable(name: str) -> str:
    """Fold a name, and write decimals with a dot, as tree.yaml does."""
    return re.sub(r"(?<=\d),(?=\d)", ".", fold(name))


def _fits(rule: LeafRule, text: str) -> bool:
    return (
        (not rule.starts_with or any(_starts_with(entry, text) for entry in rule.starts_with))
        and all(_has_word(word, text) for word in rule.include)
        and (not rule.any_of or any(_has_word(word, text) for word in rule.any_of))
        and not any(_has_word(word, text) for word in rule.exclude)
    )


def _has_word(word: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None


def _starts_with(entry: str, text: str) -> bool:
    return re.match(rf"{re.escape(entry)}(?!\w)", text) is not None


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
                        include=tuple(product_type.get("include", ())),
                        exclude=tuple(product_type.get("exclude", ())),
                        size=size,
                        aliases=tuple(product_type.get("aliases", ())),
                        group=category.get("group", ""),
                        any_of=tuple(product_type.get("any_of", ())),
                        starts_with=tuple(product_type.get("starts_with", ())),
                    )
                )
    return rules
