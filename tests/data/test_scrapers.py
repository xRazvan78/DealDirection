import copy
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from dealdata import scrape
from dealdata.normalize import RawProduct, Size
from dealdata.scrape import Blocked, PoliteClient, build_snapshot, unique_products
from dealdata.scrape_auchan import parse_auchan, read_raw_auchan, scrape_auchan, search_terms
from dealdata.scrape_carrefour import parse_carrefour, read_raw_carrefour, scrape_carrefour
from dealdata.tree import LeafRule, category_nodes, load_tree

FIXTURES = Path(__file__).parents[1] / "fixtures"
REAL_TREE = Path(__file__).parents[2] / "data" / "tree.yaml"
SNAPSHOT = Path(__file__).parents[2] / "data" / "snapshot" / "products.json"
CATEGORY_URL = "https://carrefour.ro/bacanie-carrefour/alimente/lapte-si-derivate-lapte-uht/"


@pytest.fixture
def auchan_payload() -> list[dict]:
    return json.loads((FIXTURES / "auchan_search.json").read_text(encoding="utf-8"))


@pytest.fixture
def carrefour_html() -> str:
    return (FIXTURES / "carrefour_category.html").read_text(encoding="utf-8")


def client_for(handler, sleep=lambda seconds: None, clock=lambda: 0.0) -> PoliteClient:
    return PoliteClient(transport=httpx.MockTransport(handler), sleep=sleep, clock=clock)


def test_parse_auchan_reads_the_real_fixture(auchan_payload: list[dict]) -> None:
    products = parse_auchan(auchan_payload)

    assert len(products) == 3
    assert products[0] == RawProduct(
        store="Auchan",
        name="Lapte integral Albalact, 3.5% grasime, 1 l",
        brand="Albalact",
        barcode=None,
        price=Decimal("8.5"),
        image_url=None,
        source_url="https://www.auchan.ro/lapte-de-vaca-albalact-3-5-grasime-1-l/p",
    )


def test_parse_auchan_keeps_prices_as_exact_decimals(auchan_payload: list[dict]) -> None:
    payload = copy.deepcopy(auchan_payload)
    payload[0]["items"][0]["sellers"][0]["commertialOffer"]["Price"] = 8.49

    assert parse_auchan(payload)[0].price == Decimal("8.49")


def test_parse_auchan_skips_out_of_stock_products(auchan_payload: list[dict]) -> None:
    payload = copy.deepcopy(auchan_payload)
    payload[0]["items"][0]["sellers"][0]["commertialOffer"]["AvailableQuantity"] = 0

    names = [product.name for product in parse_auchan(payload)]

    assert "Lapte integral Albalact, 3.5% grasime, 1 l" not in names
    assert len(names) == 2


def test_parse_auchan_skips_products_with_no_offer(auchan_payload: list[dict]) -> None:
    payload = copy.deepcopy(auchan_payload)
    payload[0]["items"] = []

    assert len(parse_auchan(payload)) == 2


def test_parse_carrefour_reads_the_real_fixture(carrefour_html: str) -> None:
    products = parse_carrefour(carrefour_html, CATEGORY_URL)

    assert len(products) == 4
    assert products[0] == RawProduct(
        store="Carrefour",
        name="Bautura din ovaz 1.5% grasimi, vegan, Oatly, 1L",
        brand=None,
        barcode=None,
        price=Decimal("18.49"),
        image_url=None,
        source_url="https://carrefour.ro/produse/bautura-din-ovaz-1-5-grasimi-vegan-oatly-1l-19-15516282",
    )


def test_parse_carrefour_uses_the_normal_price_not_the_loyalty_price(
    carrefour_html: str,
) -> None:
    products = parse_carrefour(carrefour_html, CATEGORY_URL)

    assert products[2].name == "Bautura Bio Migdale 1L The Bridge"
    assert products[2].price == Decimal("27.99")


def test_parse_carrefour_skips_items_without_a_price() -> None:
    html = """
    <ol class="products list">
      <li class="product">
        <div class="productItem-name"><a href="https://carrefour.ro/produse/x" title="X 1L">X 1L</a></div>
      </li>
    </ol>
    """

    assert parse_carrefour(html, CATEGORY_URL) == []


def test_parse_carrefour_returns_nothing_for_a_page_with_no_products() -> None:
    assert parse_carrefour("<html><body>Nimic</body></html>", CATEGORY_URL) == []


def test_polite_client_sends_the_generic_user_agent() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["agent"] = request.headers["user-agent"]
        return httpx.Response(200, text="ok")

    client_for(handler).get("https://example.com/")

    assert seen["agent"] == "DealDirection/0.1"


def test_polite_client_waits_a_second_between_requests() -> None:
    now = [100.0]
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    client = client_for(
        lambda request: httpx.Response(200, text="ok"), sleep=sleep, clock=lambda: now[0]
    )

    client.get("https://example.com/1")
    now[0] += 0.25
    client.get("https://example.com/2")

    assert sleeps == [pytest.approx(0.75)]


def test_polite_client_doesnt_wait_when_enough_time_has_passed() -> None:
    now = [100.0]
    sleeps: list[float] = []
    client = client_for(
        lambda request: httpx.Response(200, text="ok"), sleep=sleeps.append, clock=lambda: now[0]
    )

    client.get("https://example.com/1")
    now[0] += 5
    client.get("https://example.com/2")

    assert sleeps == []


def test_polite_client_accepts_auchans_partial_content_status() -> None:
    response = client_for(lambda request: httpx.Response(206, text="[]")).get(
        "https://example.com/"
    )

    assert response.text == "[]"


@pytest.mark.parametrize("status", [403, 404, 429, 500, 503])
def test_polite_client_stops_on_an_error_status(status: int) -> None:
    client = client_for(lambda request: httpx.Response(status))

    with pytest.raises(Blocked, match=str(status)):
        client.get("https://example.com/")


def test_unique_products_keeps_the_first_of_each_store_and_name() -> None:
    def product(store: str, name: str, price: str) -> RawProduct:
        return RawProduct(store, name, None, None, Decimal(price), None, "https://example.com")

    first = product("Auchan", "Lapte 1 l", "8")
    repeat = product("Auchan", "Lapte 1 l", "9")
    other_store = product("Carrefour", "Lapte 1 l", "7")

    assert unique_products([first, repeat, other_store]) == [first, other_store]


def test_search_terms_has_one_term_per_type() -> None:
    size = Size(Decimal("1"), "l")
    rule = LeafRule(("Lapte", "3.5%", "1 l"), ("lapte", "3.5%"), (), size, ())
    same_type = LeafRule(("Lapte", "3.5%", "2 l"), ("lapte", "3.5%"), (), size, ())
    other = LeafRule(("Unt", "Unt", "1 l"), ("unt",), (), size, ())

    assert search_terms([rule, same_type, other]) == ["lapte 3.5%", "unt"]


def test_scrape_auchan_saves_raw_output_before_parsing(
    tmp_path: Path, auchan_payload: list[dict]
) -> None:
    queries: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(parse_qs(urlparse(str(request.url)).query))
        return httpx.Response(206, json=auchan_payload)

    products = scrape_auchan(client_for(handler), ["lapte 3.5%"], tmp_path)

    assert queries == [{"ft": ["lapte 3.5%"], "_from": ["0"], "_to": ["49"]}]
    assert len(products) == 3
    assert json.loads((tmp_path / "auchan_000.json").read_text(encoding="utf-8")) == auchan_payload


def test_scrape_auchan_sends_spaces_as_percent_20(tmp_path: Path) -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(206, json=[])

    scrape_auchan(client_for(handler), ["bautura ovaz"], tmp_path)

    # Auchan answers 400 to the "+" form of a space.
    assert "ft=bautura%20ovaz" in urls[0]


def sold_at(store: str, name: str, price: str = "8.50") -> RawProduct:
    return RawProduct(store, name, "Marca", None, Decimal(price), None, "https://example.com/p")


MILK_RULES = [
    LeafRule(
        ("Lapte", "3.5%", "1 l"),
        ("lapte", "3.5%"),
        (),
        Size(Decimal("1"), "l"),
        (),
        group="Lactate și ouă",
    ),
    LeafRule(
        ("Lapte", "1.5%", "1 l"),
        ("lapte", "1.5%"),
        (),
        Size(Decimal("1"), "l"),
        (),
        group="Lactate și ouă",
    ),
]


def test_build_snapshot_describes_each_product_for_the_load() -> None:
    products = [
        sold_at("Auchan", "Lapte 3.5% Albalact, 1 l", "8.50"),
        sold_at("Carrefour", "Lapte 3,5% Zuzu 1L", "9.10"),
    ]

    assert build_snapshot(products, MILK_RULES, date(2026, 11, 6))[0] == {
        "store": "Auchan",
        "name": "Lapte 3.5% Albalact, 1 l",
        "brand": "Marca",
        "price": "8.50",
        "unit": "l",
        "source_url": "https://example.com/p",
        "path": ["Lactate și ouă", "Lapte", "3.5%", "1 l"],
        "updated_at": "2026-11-06",
    }


def test_build_snapshot_keeps_products_sold_by_only_one_store() -> None:
    products = [
        sold_at("Auchan", "Lapte 3.5% Albalact, 1 l"),
        sold_at("Carrefour", "Lapte 3.5% Zuzu, 1 l"),
        sold_at("Auchan", "Lapte 1.5% Albalact, 1 l"),
    ]

    names = [item["name"] for item in build_snapshot(products, MILK_RULES, date(2026, 11, 6))]

    assert names == [
        "Lapte 3.5% Albalact, 1 l",
        "Lapte 3.5% Zuzu, 1 l",
        "Lapte 1.5% Albalact, 1 l",
    ]


def test_build_snapshot_leaves_out_products_with_no_size_or_leaf() -> None:
    products = [
        sold_at("Auchan", "Lapte 3.5% Albalact"),
        sold_at("Carrefour", "Paine alba, 1 l"),
    ]

    assert build_snapshot(products, MILK_RULES, date(2026, 11, 6)) == []


def test_search_terms_never_send_an_empty_search() -> None:
    size = Size(Decimal("1"), "l")
    only_alternatives = LeafRule(("Suc", "Altele", "1 l"), (), (), size, (), any_of=("suc", "nectar"))

    assert search_terms([only_alternatives]) == ["suc"]


def test_read_raw_auchan_uses_saved_files_only(tmp_path: Path, auchan_payload: list[dict]) -> None:
    (tmp_path / "auchan_000.json").write_text(json.dumps(auchan_payload), encoding="utf-8")

    assert len(read_raw_auchan(tmp_path)) == 3


def test_read_raw_carrefour_uses_saved_files_only(tmp_path: Path, carrefour_html: str) -> None:
    (tmp_path / "carrefour_000_p1.html").write_text(carrefour_html, encoding="utf-8")

    assert len(read_raw_carrefour(tmp_path)) == 4


def write_offline_project(data_dir: Path, auchan: list[dict], carrefour: str) -> Path:
    raw_dir = data_dir / "raw" / "2026-11-05"
    raw_dir.mkdir(parents=True)
    (data_dir / "snapshot").mkdir()
    (raw_dir / "auchan_000.json").write_text(json.dumps(auchan), encoding="utf-8")
    (raw_dir / "carrefour_000_p1.html").write_text(carrefour, encoding="utf-8")
    (data_dir / "tree.yaml").write_text(
        """
categories:
  - name: Lapte
    group: Lactate
    types:
      - name: Toate
        any_of: [lapte, bautura]
        sizes: ["1 l"]
""",
        encoding="utf-8",
    )
    return raw_dir


def test_offline_run_builds_the_snapshot_without_any_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auchan_payload: list[dict],
    carrefour_html: str,
) -> None:
    write_offline_project(tmp_path, auchan_payload, carrefour_html)
    monkeypatch.setattr(scrape, "DATA_DIR", tmp_path)
    monkeypatch.setattr(scrape, "PoliteClient", refuse_client)

    assert scrape.main(["--offline"]) == 0

    items = json.loads((tmp_path / "snapshot" / "products.json").read_text(encoding="utf-8"))
    assert {item["store"] for item in items} == {"Auchan", "Carrefour"}


def test_offline_run_dates_products_from_the_raw_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auchan_payload: list[dict],
    carrefour_html: str,
) -> None:
    write_offline_project(tmp_path, auchan_payload, carrefour_html)
    monkeypatch.setattr(scrape, "DATA_DIR", tmp_path)
    monkeypatch.setattr(scrape, "PoliteClient", refuse_client)

    scrape.main(["--offline"])

    items = json.loads((tmp_path / "snapshot" / "products.json").read_text(encoding="utf-8"))
    assert items[0]["updated_at"] == "2026-11-05"


def refuse_client() -> None:
    raise AssertionError("An offline run must not create an HTTP client")


def test_real_snapshot_has_every_placed_product() -> None:
    items = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert len(items) >= 2700


def test_real_snapshot_has_at_least_30_leaves_sold_by_both_stores() -> None:
    items = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    stores_per_leaf: dict[tuple[str, ...], set[str]] = {}
    for item in items:
        stores_per_leaf.setdefault(tuple(item["path"]), set()).add(item["store"])

    shared = [stores for stores in stores_per_leaf.values() if len(stores) == 2]

    assert len(shared) >= 30


def test_real_snapshot_paths_match_category_rows() -> None:
    items = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    leaves = {
        node.path for node in category_nodes(load_tree(REAL_TREE)) if node.level == "size"
    }

    assert all(tuple(item["path"]) in leaves for item in items)


def test_real_snapshot_keeps_to_names_and_prices() -> None:
    items = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert all("image_url" not in item and "barcode" not in item for item in items)


def test_real_snapshot_has_one_row_per_store_and_name() -> None:
    items = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    keys = [(item["store"], item["name"]) for item in items]

    assert len(keys) == len(set(keys))


def test_real_tree_writes_small_sizes_in_grams_and_millilitres() -> None:
    paths = {rule.path for rule in load_tree(REAL_TREE)}

    assert ("Iaurt", "Natural", "400 g") in paths
    assert ("Lapte", "3.5%", "500 ml") in paths
    assert not any(path[2].startswith("0.") for path in paths)


def refuse_requests(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"Unexpected request to {request.url}")


def test_scrape_auchan_reuses_saved_raw_output(tmp_path: Path, auchan_payload: list[dict]) -> None:
    (tmp_path / "auchan_000.json").write_text(json.dumps(auchan_payload), encoding="utf-8")

    products = scrape_auchan(client_for(refuse_requests), ["lapte"], tmp_path)

    assert len(products) == 3


def test_scrape_carrefour_reuses_saved_raw_pages(tmp_path: Path, carrefour_html: str) -> None:
    (tmp_path / "carrefour_000_p1.html").write_text(carrefour_html, encoding="utf-8")

    products = scrape_carrefour(
        client_for(refuse_requests), [CATEGORY_URL], tmp_path, max_pages=1
    )

    assert len(products) == 4


def test_scrape_carrefour_follows_pages_until_nothing_is_new(
    tmp_path: Path, carrefour_html: str
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, text=carrefour_html)

    products = scrape_carrefour(client_for(handler), [CATEGORY_URL], tmp_path)

    assert requested == [CATEGORY_URL, f"{CATEGORY_URL}?p=2"]
    assert len(products) == 4
    assert (tmp_path / "carrefour_000_p1.html").read_text(encoding="utf-8") == carrefour_html


def test_scrape_carrefour_keeps_to_the_page_limit(tmp_path: Path) -> None:
    pages = iter(range(100))

    def handler(request: httpx.Request) -> httpx.Response:
        page = next(pages)
        return httpx.Response(
            200,
            text=f"""
            <ol class="products list"><li class="product">
              <div class="productItem-name"><a href="https://carrefour.ro/produse/{page}" title="P{page}">P{page}</a></div>
              <div class="price" data-price-amount="1,00"></div>
            </li></ol>
            """,
        )

    products = scrape_carrefour(client_for(handler), [CATEGORY_URL], tmp_path, max_pages=3)

    assert len(products) == 3
