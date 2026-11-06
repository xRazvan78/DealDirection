from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from dealdata.normalize import RawProduct, Size, parse_size
from dealdata.tree import CategoryNode, LeafRule, category_nodes, load_tree

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


@pytest.mark.parametrize(
    ("name", "amount"),
    [
        ("Hartie igienica Auchan 16 role, 3 straturi", "16"),
        ("Hartie igienica Pufina 3 straturi 8 role", "8"),
        ("Ceai negru Lipton Fructe de padure, 20 plicuri", "20"),
        ("Ceai Twinings din plante, 18 pliculete", "18"),
        ("10 Capsule Aluminiu Segafredo Espresso", "10"),
        ("Detergent de rufe capsule Ariel PODS, 60 Spalari", "60"),
        ("Persil Discs Universal 2x42 spalari", "84"),
        ("Detergent Dero 20 spălări", "20"),
    ],
)
def test_parse_size_counts_packs_sold_by_number(name: str, amount: str) -> None:
    assert parse_size(name) == Size(Decimal(amount), "buc")


def test_parse_size_allows_de_before_the_unit() -> None:
    assert parse_size("Hartie igienica umeda Auchan, 50 de bucati") == Size(Decimal("50"), "buc")


def test_parse_size_reads_a_size_straight_after_a_comma() -> None:
    assert parse_size("Cafea Macinata Crema Classica ,250G") == Size(Decimal("0.25"), "kg")


def test_parse_size_ignores_paper_layers() -> None:
    assert parse_size("Hartie igienica 3 straturi") is None


def test_parse_size_ignores_fat_percentage() -> None:
    name = "Lapte integral Albalact, 3.5% grasime, 1 l"

    assert parse_size(name) == Size(Decimal("1"), "l")


def test_parse_size_rounds_to_the_three_decimals_the_database_keeps() -> None:
    assert parse_size("Inghetata 6 x 50,1 ml") == Size(Decimal("0.301"), "l")


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


def test_load_tree_reads_the_group_above_each_category(tmp_path: Path) -> None:
    tree = tmp_path / "tree.yaml"
    tree.write_text(
        """
categories:
  - name: Lapte
    group: Lactate și ouă
    types:
      - name: "3.5%"
        include: [lapte]
        sizes: ["1 l"]
""",
        encoding="utf-8",
    )

    assert load_tree(tree)[0].group == "Lactate și ouă"


def test_load_tree_reads_alternative_words(tmp_path: Path) -> None:
    tree = tmp_path / "tree.yaml"
    tree.write_text(
        """
categories:
  - name: Suc
    types:
      - name: Altele
        include: [natural]
        any_of: [suc, sucuri]
        sizes: ["1 l"]
""",
        encoding="utf-8",
    )

    assert load_tree(tree)[0].any_of == ("suc", "sucuri")


def test_load_tree_reads_required_first_words(tmp_path: Path) -> None:
    tree = tmp_path / "tree.yaml"
    tree.write_text(
        """
categories:
  - name: Unt
    types:
      - name: Unt
        include: [unt]
        starts_with: [unt, margarina]
        sizes: ["200 g"]
""",
        encoding="utf-8",
    )

    assert load_tree(tree)[0].starts_with == ("unt", "margarina")


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


def test_real_tree_has_at_least_25_categories() -> None:
    categories = {rule.path[0] for rule in load_tree(REAL_TREE)}

    assert len(categories) >= 25


def test_real_tree_puts_every_leaf_in_a_big_group() -> None:
    rules = load_tree(REAL_TREE)

    assert all(rule.group for rule in rules)
    assert 8 <= len({rule.group for rule in rules}) <= 16


def test_real_tree_puts_milk_under_dairy() -> None:
    groups = {rule.path: rule.group for rule in load_tree(REAL_TREE)}

    assert groups[("Lapte", "3.5%", "1 l")] == "Lactate și ouă"


def test_real_tree_has_at_least_30_leaves() -> None:
    assert len(load_tree(REAL_TREE)) >= 30


def test_real_tree_contains_the_milk_leaf_from_the_task() -> None:
    paths = {rule.path for rule in load_tree(REAL_TREE)}

    assert ("Lapte", "3.5%", "1 l") in paths


def test_real_tree_paths_are_unique() -> None:
    paths = [rule.path for rule in load_tree(REAL_TREE)]

    assert len(paths) == len(set(paths))


def test_category_nodes_turn_a_leaf_into_database_rows() -> None:
    rule = LeafRule(
        path=("Lapte", "3.5%", "1 l"),
        include=("lapte",),
        exclude=(),
        size=Size(Decimal("1"), "l"),
        aliases=("lapte",),
        group="Lactate și ouă",
    )

    assert category_nodes([rule]) == [
        CategoryNode(("Lactate și ouă",), "category"),
        CategoryNode(("Lactate și ouă", "Lapte"), "category"),
        CategoryNode(("Lactate și ouă", "Lapte", "3.5%"), "type"),
        CategoryNode(
            ("Lactate și ouă", "Lapte", "3.5%", "1 l"),
            "size",
            size_amount=Decimal("1"),
            size_unit="l",
            aliases=("lapte",),
        ),
    ]


def test_category_nodes_share_parents_between_leaves() -> None:
    def leaf(size_text: str) -> LeafRule:
        return LeafRule(("Lapte", "3.5%", size_text), (), (), Size(Decimal("1"), "l"), (), "Lactate")

    nodes = category_nodes([leaf("1 l"), leaf("2 l")])

    assert [node.path[-1] for node in nodes] == ["Lactate", "Lapte", "3.5%", "1 l", "2 l"]


def test_category_node_names_its_parent() -> None:
    assert CategoryNode(("Lactate", "Lapte"), "category").parent == ("Lactate",)
    assert CategoryNode(("Lactate",), "category").parent is None


def test_real_tree_fits_the_categories_table() -> None:
    nodes = category_nodes(load_tree(REAL_TREE))
    paths = {node.path for node in nodes}

    assert len(paths) == len(nodes)
    for node in nodes:
        assert node.level in {"category", "type", "size"}
        assert len(node.path[-1]) <= 100, node.path
        assert node.parent is None or node.parent in paths, node.path


def test_real_tree_sizes_fit_the_categories_table() -> None:
    sizes = [node for node in category_nodes(load_tree(REAL_TREE)) if node.level == "size"]

    for node in sizes:
        assert node.size_unit in {"l", "kg", "buc"}, node.path
        # size_amount is NUMERIC(10, 3), so a fourth decimal would be rounded away.
        assert node.size_amount == node.size_amount.quantize(Decimal("0.001")), node.path


def test_real_tree_words_are_already_folded() -> None:
    for rule in load_tree(REAL_TREE):
        assert rule.include or rule.any_of, rule.path
        for word in (*rule.include, *rule.any_of, *rule.starts_with, *rule.exclude, *rule.aliases):
            assert word == word.lower() and word.isascii(), (rule.path, word)
