from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from dealdata.normalize import RawProduct, Size, parse_size
from dealdata.tree import LeafRule, load_tree

REAL_TREE = Path(__file__).parents[2] / "data" / "tree.yaml"


@pytest.mark.parametrize(
    ("name", "amount", "unit"),
    [
        ("1 l", "1", "l"),
        ("500 ml", "0.5", "l"),
        ("1,5kg", "1.5", "kg"),
        ("200g", "0.2", "kg"),
        ("6x0.5l", "3", "l"),
        ("10 buc", "10", "buc"),
    ],
)
def test_parse_size_reads_task_examples(name: str, amount: str, unit: str) -> None:
    assert parse_size(name) == Size(Decimal(amount), unit)


@pytest.mark.parametrize(
    ("name", "amount", "unit"),
    [
        ("Apa plata 6 x 500 ml", "3", "l"),
        ("Iaurt 4×125g", "0.5", "kg"),
        ("Suc 2*1,5 l", "3", "l"),
        ("Vin 75 cl", "0.75", "l"),
        ("Bere 5 dl", "0.5", "l"),
        ("Oua 10 bucati", "10", "buc"),
        ("Oua 6 bucăți", "6", "buc"),
        ("Lamai 3 buc.", "3", "buc"),
        ("Zahar 1 KG", "1", "kg"),
        ("Cafea 250 gr", "0.25", "kg"),
        ("Ulei 2 litri", "2", "l"),
    ],
)
def test_parse_size_reads_store_name_variants(name: str, amount: str, unit: str) -> None:
    assert parse_size(name) == Size(Decimal(amount), unit)


def test_parse_size_ignores_fat_percentage() -> None:
    name = "Lapte integral Albalact, 3.5% grasime, 1 l"

    assert parse_size(name) == Size(Decimal("1"), "l")


def test_parse_size_keeps_decimals_exact() -> None:
    size = parse_size("Ulei 0,33 l")

    assert size is not None
    assert size.amount == Decimal("0.33")
    assert isinstance(size.amount, Decimal)


@pytest.mark.parametrize(
    "name",
    [
        "Paine alba",
        "Lapte 3.5%",
        "Vitamina C 500 mg",
        "Hartie A4 lucioasa",
        "",
    ],
)
def test_parse_size_returns_none_without_a_size(name: str) -> None:
    assert parse_size(name) is None


def test_raw_product_holds_scraped_fields() -> None:
    product = RawProduct(
        store="Auchan",
        name="Lapte 1 l",
        brand="Albalact",
        barcode="5941234567890",
        price=Decimal("8.49"),
        image_url="https://example.com/lapte.jpg",
        source_url="https://example.com/lapte",
    )

    assert product.price == Decimal("8.49")
    with pytest.raises(FrozenInstanceError):
        product.price = Decimal("1")  # type: ignore[misc]


def test_load_tree_creates_one_leaf_per_size(tmp_path: Path) -> None:
    tree = tmp_path / "tree.yaml"
    tree.write_text(
        """
categories:
  - name: Brânză
    types:
      - name: Telemea
        include: [telemea]
        exclude: [topita]
        sizes: ["400 g", "1 kg"]
        aliases: [branza telemea]
""",
        encoding="utf-8",
    )

    assert load_tree(tree) == [
        LeafRule(
            path=("Brânză", "Telemea", "400 g"),
            include=("telemea",),
            exclude=("topita",),
            size=Size(Decimal("0.4"), "kg"),
            aliases=("branza telemea",),
        ),
        LeafRule(
            path=("Brânză", "Telemea", "1 kg"),
            include=("telemea",),
            exclude=("topita",),
            size=Size(Decimal("1"), "kg"),
            aliases=("branza telemea",),
        ),
    ]


def test_load_tree_treats_missing_exclude_and_aliases_as_empty(tmp_path: Path) -> None:
    tree = tmp_path / "tree.yaml"
    tree.write_text(
        """
categories:
  - name: Ouă
    types:
      - name: Găini
        include: [oua]
        sizes: ["10 buc"]
""",
        encoding="utf-8",
    )

    rule = load_tree(tree)[0]

    assert rule.exclude == ()
    assert rule.aliases == ()


def test_load_tree_rejects_an_unreadable_size(tmp_path: Path) -> None:
    tree = tmp_path / "tree.yaml"
    tree.write_text(
        """
categories:
  - name: Lapte
    types:
      - name: "3.5%"
        include: [lapte]
        sizes: ["un litru"]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="un litru"):
        load_tree(tree)


def test_real_tree_has_25_to_35_categories() -> None:
    categories = {rule.path[0] for rule in load_tree(REAL_TREE)}

    assert 25 <= len(categories) <= 35


def test_real_tree_has_at_least_30_leaves() -> None:
    assert len(load_tree(REAL_TREE)) >= 30


def test_real_tree_contains_the_milk_leaf_from_the_task() -> None:
    paths = {rule.path for rule in load_tree(REAL_TREE)}

    assert ("Lapte", "3.5%", "1 l") in paths


def test_real_tree_paths_are_unique() -> None:
    paths = [rule.path for rule in load_tree(REAL_TREE)]

    assert len(paths) == len(set(paths))


def test_real_tree_words_are_already_folded() -> None:
    for rule in load_tree(REAL_TREE):
        assert rule.include, rule.path
        for word in (*rule.include, *rule.exclude, *rule.aliases):
            assert word == word.lower() and word.isascii(), (rule.path, word)
