import json
import re
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from app.textutil import fold
from dealdata.normalize import RawProduct, Size, parse_size
from dealdata.tree import CategoryNode, LeafRule, category_nodes, classify, load_tree

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


ONE_LITRE = Size(Decimal("1"), "l")


def product_named(name: str) -> RawProduct:
    return RawProduct("Auchan", name, None, None, Decimal("1"), None, "https://example.com")


def rule(
    name: str = "Regula",
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    any_of: tuple[str, ...] = (),
    starts_with: tuple[str, ...] = (),
    size: Size = ONE_LITRE,
) -> LeafRule:
    return LeafRule(
        (name, name, "1 l"), include, exclude, size, (), any_of=any_of, starts_with=starts_with
    )


def classified(name: str, *rules: LeafRule) -> LeafRule | None:
    return classify(product_named(name), ONE_LITRE, list(rules))


def test_classify_puts_real_milk_in_its_leaf() -> None:
    name = "Lapte integral Albalact, 3.5% grasime, 1 l"
    size = parse_size(name)

    assert size is not None
    leaf = classify(product_named(name), size, load_tree(REAL_TREE))

    assert leaf is not None
    assert leaf.path == ("Lapte", "3.5%", "1 l")


def test_classify_leaves_out_baby_cleansing_lotion() -> None:
    name = "Lapte de curatare Pouce, 300ml"
    size = parse_size(name)

    assert size is not None
    assert classify(product_named(name), size, load_tree(REAL_TREE)) is None


def test_classify_needs_every_include_word() -> None:
    needs_both = rule(include=("lapte", "3.5%"))

    assert classified("Lapte integral, 3.5% grasime", needs_both) == needs_both
    assert classified("Lapte integral", needs_both) is None


def test_classify_rejects_an_exclude_word() -> None:
    assert classified("Lapte de curatare", rule(include=("lapte",), exclude=("curatare",))) is None


def test_classify_needs_one_any_of_word() -> None:
    juice = rule(any_of=("suc", "sucuri"))

    assert classified("Sucuri naturale", juice) == juice
    assert classified("Apa plata", juice) is None


def test_classify_needs_the_name_to_start_with_a_starts_with_entry() -> None:
    butter = rule(include=("unt",), starts_with=("unt", "margarina"))

    assert classified("Unt de masa Pilos", butter) == butter
    assert classified("Sampon cu unt de shea", butter) is None


def test_classify_accepts_a_starts_with_phrase() -> None:
    meal = rule(starts_with=("pui cu",))

    assert classified("Pui cu orez basmati", meal) == meal
    assert classified("Pui intreg", meal) is None


def test_classify_doesnt_treat_a_longer_word_as_a_starts_with_match() -> None:
    assert classified("Untura de porc", rule(starts_with=("unt",))) is None


def test_classify_matches_whole_words_only() -> None:
    butter = rule(include=("unt",))

    assert classified("Untura de porc", butter) is None
    assert classified("Crema de unt", butter) == butter


def test_classify_ignores_case_and_diacritics() -> None:
    cheese = rule(include=("branza",))

    assert classified("BRÂNZĂ de vaci", cheese) == cheese


def test_classify_reads_a_comma_percentage() -> None:
    milk = rule(include=("lapte", "3.5%"))

    assert classified("Lapte integral 3,5% grasime", milk) == milk


def test_classify_needs_the_leaf_size_to_match() -> None:
    half_litre = rule(include=("lapte",), size=Size(Decimal("0.5"), "l"))

    assert classified("Lapte integral", half_litre) is None


def test_classify_treats_equal_sizes_with_different_decimals_as_the_same() -> None:
    litre = rule(include=("lapte",))

    assert classify(product_named("Lapte"), Size(Decimal("1.000"), "l"), [litre]) == litre


def test_classify_takes_the_first_matching_rule() -> None:
    chocolate = rule("Ciocolata", include=("ciocolata",))
    milk = rule("Lapte", include=("lapte",))

    assert classified("Ciocolata cu lapte", chocolate, milk) == chocolate


def test_classify_keeps_a_chocolate_with_milk_out_of_the_milk_leaf() -> None:
    name = "Ciocolata cu lapte Heidi, 100 g"
    size = parse_size(name)

    assert size is not None
    leaf = classify(product_named(name), size, load_tree(REAL_TREE))

    assert leaf is not None
    assert leaf.path[0] == "Ciocolată"


def category_of(name: str) -> str | None:
    size = parse_size(name)
    assert size is not None, name
    leaf = classify(product_named(name), size, load_tree(REAL_TREE))
    return leaf.path[0] if leaf else None


@pytest.mark.parametrize(
    ("name", "category"),
    [
        ("Lapte praf integral Dr. Oetker 250g", "Lapte"),
        ("Lapte de crestere Nestle NAN Optipro 5, 3+ ani, 700 g", "Hrană bebeluși"),
        ("Apa plata Vedda Baby, 1 l", "Apă"),
        ("Rezerva detergent de vase cu otet Svelto, 1 l", "Detergent"),
        ("Detergent de vase Sano Spark migdale, 1L", "Detergent"),
        ("Detergent de vase cu bicarbonat Triumf, 500 ml", "Detergent"),
        ("Otet din cidru de mere De Nigris 500 ml", "Oțet"),
        ("Faina alba pentru prajituri Auchan, tip 000, 1 kg", "Făină"),
        ("Faina alba de grau 550 pentru pizza Panzani, 1kg", "Făină"),
        ("Paine din faina alba de grau Vel Pitar, feliata 600 g", "Pâine"),
        ("Ulei din turte de masline Costa d'Oro 1L", "Ulei"),
        ("Ulei de masline extravirgin 250 ml Kaiser Franz Josef", "Ulei"),
        ("Bautura din ovaz Alpro, 1 l", "Lapte"),
        ("Knorr Cub Vita 10 Buc 5L 100G", "Supe"),
        ("Bautura necarbogazoasa cu extract de ceai negru si lamaie, 1.5 l", "Ceai"),
    ],
)
def test_real_tree_files_a_product_by_what_it_is(name: str, category: str) -> None:
    assert category_of(name) == category


@pytest.mark.parametrize(
    ("name", "wrong"),
    [
        ("Lapte praf integral Dr.Oetker 130g", "Hrană bebeluși"),
        ("Lotiune hidratanta Auchan Baby Bio, cu ulei de masline, 200 ml", "Hrană bebeluși"),
        ("Lotiune tonica Garnier Vitamin C cu efect de iluminare, 200 ml", "Băuturi răcoritoare"),
        ("Mirin din vin de orez Saitaku 150ml", "Vin"),
        ("Dr.Oetker Ciocco Latte cu Rom 21g", "Băuturi spirtoase"),
        ("Soia texturat cuburi Inedit 100 g", "Supe"),
        ("Crochete vegetale din soia Inedit in sos tomat 155 g", "Sosuri"),
        ("Dropsuri fara zahar cu aroma de capsuni si frisca 40 g", "Frișcă"),
    ],
)
def test_real_tree_keeps_a_product_out_of_a_category_it_only_mentions(
    name: str, wrong: str
) -> None:
    assert category_of(name) != wrong


def test_real_tree_gives_every_leaf_an_alias() -> None:
    missing = [rule.path for rule in load_tree(REAL_TREE) if not rule.aliases]

    assert missing == []


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


def real_leaf(name: str) -> LeafRule | None:
    size = parse_size(name)
    assert size is not None
    return classify(product_named(name), size, load_tree(REAL_TREE))


@pytest.mark.parametrize(
    ("name", "wrong"),
    [
        ("Lotiune hidratanta Auchan Baby Bio, cu ulei de masline, 200 ml", ("Ulei", "Măsline")),
        ("Lipie piadina cu ulei de masline Acqua Farina, 360 g", ("Ulei", "Măsline")),
        ("Solutie pentru lemn Rivex, cu ulei de masline, 750 ml", ("Ulei", "Măsline")),
        (
            "Trufe feliate Carpaccio in ulei de masline extra virgin Geofoods, 80 g",
            ("Ulei", "Măsline"),
        ),
        (
            "Cous cous mediteranean cu legume si ulei de masline Baneasa, 130 g",
            ("Ulei", "Măsline"),
        ),
        ("Balsam corporal cu ulei de masline Natigo The Ritual Of Melasti, 400 ml", ("Ulei", "Măsline")),
        ("Gel de dus cu ulei de masline Natigo The Ritual Of Melasti, 400 ml", ("Ulei", "Măsline")),
        ("Sano Maxima gel capsule soft silk (40 capsule)", ("Cafea", "Capsule (alte branduri)")),
        ("Ceai negru cu aroma de biscuit Taylors of Harrogate, 40 plicuri", ("Biscuiți", "Biscuiți")),
        ("Risotto cu trufe Riso Scotti 210g", ("Ciocolată", "Praline")),
        ("Paste tagliatelle Carrefour Extra cu aroma de trufe, 250g", ("Ciocolată", "Praline")),
        ("Otet crema balsamica Greek Land cu trufe 250ml", ("Ciocolată", "Praline")),
        ("Paine cu malai si maia Auchan, 500 g", ("Mălai", "Mălai")),
        ("Gnocchi din cartofi cu orez si malai, 400g Felicia", ("Mălai", "Mălai")),
        ("Lapte UHT Meggle cu ciocolata 500ml", ("Ciocolată", "Cu lapte")),
        ("Tassimo Milka 8 buc", ("Ciocolată", "Alte sortimente")),
        ("Mini foietaj cu telemea Grane Aurii, 500 g", ("Brânză", "Telemea")),
        ("Minipateuri cu umplutura din branza telemea, crud congelat, 500 g", ("Brânză", "Telemea")),
        (
            "Amestec de legume pentru prajit in tigaie, cartofi si ciuperci, 400g",
            ("Condimente", "Condimente"),
        ),
    ],
)
def test_classify_keeps_products_out_of_leaves_that_only_share_a_word(
    name: str, wrong: tuple[str, str]
) -> None:
    leaf = real_leaf(name)

    assert leaf is None or leaf.path[:2] != wrong


@pytest.mark.parametrize(
    "name",
    [
        "Bucati de ton in suc natur Rio Mare 160 g",
        "Conserva de ton Rio Mare in suc natural, 3 x 80 g",
    ],
)
def test_classify_puts_tuna_in_its_own_juice_with_tuna(name: str) -> None:
    leaf = real_leaf(name)

    assert leaf is not None
    assert leaf.path[:2] == ("Ton", "Conservă")


@pytest.mark.parametrize(
    "name",
    [
        "Detergent lichid de rufe Froch Sensitive Baby, 22 spalari, 1.5 l",
        "Detergent lichid de rufe Sano Maxima Power Gel Baby, 60 spalari, 3 l",
        "Igienol Detergent Lichid Dezinfectant Baby 1.8L",
        "Detergent Gel concentrat pentru rufe Maxima Baby Oat, 1500 ml, Sano",
    ],
)
def test_classify_keeps_baby_detergent_out_of_baby_food(name: str) -> None:
    leaf = real_leaf(name)

    assert leaf is None or leaf.path[0] != "Hrană bebeluși"


@pytest.mark.parametrize(
    "name",
    [
        "Ulei de masline cu trufe Monini, 250 ml",
        "Spray ulei de masline extravirgin Monini, 200 ml",
    ],
)
def test_classify_still_accepts_flavoured_olive_oil(name: str) -> None:
    leaf = real_leaf(name)

    assert leaf is not None
    assert leaf.path[:2] == ("Ulei", "Măsline")


def test_food_in_the_snapshot_has_no_household_products() -> None:
    """A word search over everything, because these slipped past checks by sample."""
    snapshot = json.loads((REAL_TREE.parent / "snapshot" / "products.json").read_text("utf-8"))
    non_food_groups = {"Curățenie și casă", "Îngrijire personală", "Animale de companie"}
    non_food_words = re.compile(
        r"\b(detergent|sampon|lotiune|gel de dus|balsam corporal|solutie|spalari)\b"
    )

    found = [
        product["name"]
        for product in snapshot
        if product["path"][0] not in non_food_groups
        and non_food_words.search(fold(product["name"]))
    ]

    assert found == []
