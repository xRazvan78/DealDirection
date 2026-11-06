from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Category, Store, StoreProduct


def select_stores(client: TestClient, *store_ids: int) -> None:
    response = client.put("/api/me/stores", json={"store_ids": list(store_ids)})
    assert response.status_code == 204


def store_ids(sample: Any) -> list[int]:
    return [store.id for store in sample.stores]


def choose_all(client: TestClient, sample: Any) -> None:
    select_stores(client, *store_ids(sample))


def products_at(client: TestClient, category_id: int, **params: str) -> dict:
    response = client.get(f"/api/categories/{category_id}/products", params=params)
    assert response.status_code == 200
    return response.json()


def search(client: TestClient, query: str) -> list[dict]:
    response = client.get("/api/search", params={"q": query})
    assert response.status_code == 200
    return response.json()


@dataclass(frozen=True)
class Tree:
    group: Category
    category: Category
    type: Category
    sizes: tuple[Category, Category]


@pytest.fixture
def tree(db: Session) -> Tree:
    """A four-level path, as the real tree has: group, category, type and size."""

    def child(parent: Category | None, name: str, level: str, **size: Any) -> Category:
        row = Category(
            parent_id=parent.id if parent else None, name=name, level=level, **size
        )
        db.add(row)
        db.flush()
        return row

    group = child(None, "Grupa Catalog", "category")
    category = child(group, "Categorie Catalog", "category")
    type_ = child(category, "Tip Catalog", "type")
    large = child(type_, "2 l", "size", size_amount=Decimal("2"), size_unit="l")
    small = child(type_, "500 ml", "size", size_amount=Decimal("0.5"), size_unit="l")
    return Tree(group, category, type_, (large, small))


def add_product(
    db: Session,
    store: Store,
    tree: Tree,
    name: str,
    price: str = "5.00",
    search_text: str | None = None,
    size: int = 0,
) -> StoreProduct:
    product = StoreProduct(
        store_id=store.id,
        size_category_id=tree.sizes[size].id,
        type_category_id=tree.type.id,
        name=name,
        brand=None,
        price=Decimal(price),
        unit="l",
        search_text=search_text or name.lower(),
    )
    db.add(product)
    db.flush()
    return product


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/stores"),
        ("put", "/api/me/stores"),
        ("get", "/api/categories"),
        ("get", "/api/categories/1/products"),
        ("get", "/api/search?q=lapte"),
    ],
)
def test_catalog_routes_need_a_login(client: TestClient, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 401


class TestStores:
    def test_lists_stores_with_their_details(self, auth_client: TestClient, sample: Any) -> None:
        stores = {store["id"]: store for store in auth_client.get("/api/stores").json()}

        assert stores[sample.stores[0].id] == {
            "id": sample.stores[0].id,
            "name": "Magazin Test A",
            "colour": "#d6001c",
            "logo": None,
            "selected": False,
        }

    def test_marks_the_selected_stores(self, auth_client: TestClient, sample: Any) -> None:
        select_stores(auth_client, sample.stores[1].id)

        stores = {store["id"]: store for store in auth_client.get("/api/stores").json()}

        assert stores[sample.stores[0].id]["selected"] is False
        assert stores[sample.stores[1].id]["selected"] is True

    def test_a_new_selection_replaces_the_old_one(
        self, auth_client: TestClient, sample: Any
    ) -> None:
        select_stores(auth_client, *store_ids(sample))

        select_stores(auth_client, sample.stores[0].id)

        selected = [s["id"] for s in auth_client.get("/api/stores").json() if s["selected"]]
        assert selected == [sample.stores[0].id]

    def test_an_empty_selection_is_allowed(self, auth_client: TestClient, sample: Any) -> None:
        select_stores(auth_client, *store_ids(sample))

        select_stores(auth_client)

        assert not any(s["selected"] for s in auth_client.get("/api/stores").json())

    def test_a_repeated_id_counts_once(self, auth_client: TestClient, sample: Any) -> None:
        store_id = sample.stores[0].id

        select_stores(auth_client, store_id, store_id)

        selected = [s["id"] for s in auth_client.get("/api/stores").json() if s["selected"]]
        assert selected == [store_id]

    def test_an_unknown_store_gives_422_and_keeps_the_selection(
        self, auth_client: TestClient, sample: Any
    ) -> None:
        choose_all(auth_client, sample)

        response = auth_client.put("/api/me/stores", json={"store_ids": [-1]})

        assert response.status_code == 422
        assert sum(s["selected"] for s in auth_client.get("/api/stores").json()) == 2

    def test_a_selection_belongs_to_one_user(
        self, auth_client: TestClient, other_client: TestClient, sample: Any
    ) -> None:
        select_stores(auth_client, *store_ids(sample))

        assert not any(s["selected"] for s in other_client.get("/api/stores").json())


class TestCategories:
    def children(self, client: TestClient, parent: Category | None = None) -> list[dict]:
        params = {"parent_id": parent.id} if parent else {}
        response = client.get("/api/categories", params=params)
        assert response.status_code == 200
        return response.json()

    def test_top_level_has_rows_with_no_parent(self, auth_client: TestClient, tree: Tree) -> None:
        top = self.children(auth_client)

        assert tree.group.id in [row["id"] for row in top]
        assert all(row["parent_id"] is None for row in top)

    def test_a_row_has_only_the_fields_the_screens_use(
        self, auth_client: TestClient, tree: Tree
    ) -> None:
        assert self.children(auth_client, tree.group) == [
            {
                "id": tree.category.id,
                "parent_id": tree.group.id,
                "name": "Categorie Catalog",
                "level": "category",
            }
        ]

    def test_walks_from_group_to_size(self, auth_client: TestClient, tree: Tree) -> None:
        category = self.children(auth_client, tree.group)[0]
        type_ = self.children(auth_client, tree.category)[0]
        size = self.children(auth_client, tree.type)[0]

        assert (category["level"], type_["level"], size["level"]) == (
            "category",
            "type",
            "size",
        )

    def test_walks_a_tree_with_no_group(self, auth_client: TestClient, sample: Any) -> None:
        assert self.children(auth_client, sample.category)[0]["id"] == sample.type.id
        assert self.children(auth_client, sample.type)[0]["id"] == sample.size.id

    def test_sizes_go_from_smallest_to_largest(self, auth_client: TestClient, tree: Tree) -> None:
        names = [row["name"] for row in self.children(auth_client, tree.type)]

        assert names == ["500 ml", "2 l"]

    def test_other_rows_go_by_name(self, auth_client: TestClient, db: Session, tree: Tree) -> None:
        db.add(Category(parent_id=tree.group.id, name="Altă Catalog", level="category"))
        db.flush()

        names = [row["name"] for row in self.children(auth_client, tree.group)]

        assert names == ["Altă Catalog", "Categorie Catalog"]

    def test_an_unknown_parent_has_no_children(self, auth_client: TestClient) -> None:
        response = auth_client.get("/api/categories", params={"parent_id": -1})

        assert response.json() == []


class TestProducts:
    def test_generic_is_the_lowest_price_at_selected_stores(
        self, auth_client: TestClient, sample: Any
    ) -> None:
        choose_all(auth_client, sample)

        found = products_at(auth_client, sample.size.id)

        assert found["generic"]["name"] == "Lapte Albalact 3.5% 1l"
        assert found["generic"]["price"] == "7.90"
        assert found["generic"]["store_name"] == "Magazin Test B"

    def test_products_go_from_cheapest_to_dearest(
        self, auth_client: TestClient, sample: Any
    ) -> None:
        choose_all(auth_client, sample)

        prices = [p["price"] for p in products_at(auth_client, sample.size.id)["products"]]

        assert prices == ["7.90", "8.50", "9.20"]

    def test_equal_prices_take_the_lowest_id(
        self, auth_client: TestClient, db: Session, sample: Any, tree: Tree
    ) -> None:
        choose_all(auth_client, sample)
        first = add_product(db, sample.stores[0], tree, "Produs Unu", "4.00")
        add_product(db, sample.stores[1], tree, "Produs Doi", "4.00")

        assert products_at(auth_client, tree.sizes[0].id)["generic"]["id"] == first.id

    def test_unselected_stores_never_appear(self, auth_client: TestClient, sample: Any) -> None:
        select_stores(auth_client, sample.stores[0].id)

        found = products_at(auth_client, sample.size.id)

        assert found["generic"]["price"] == "8.50"
        assert {p["store_id"] for p in found["products"]} == {sample.stores[0].id}

    def test_no_selected_stores_gives_a_null_generic(
        self, auth_client: TestClient, sample: Any
    ) -> None:
        assert products_at(auth_client, sample.size.id) == {"generic": None, "products": []}

    def test_a_product_has_the_fields_the_screens_use(
        self, auth_client: TestClient, db: Session, sample: Any
    ) -> None:
        sample.products[2].updated_at = datetime(2026, 11, 6, tzinfo=UTC)
        db.flush()
        choose_all(auth_client, sample)

        generic = products_at(auth_client, sample.size.id)["generic"]

        assert set(generic) == {
            "id",
            "store_id",
            "store_name",
            "name",
            "brand",
            "price",
            "image_url",
            "updated_at",
        }
        assert generic["updated_at"].startswith("2026-11-06")

    def test_brand_search_filters_products(self, auth_client: TestClient, sample: Any) -> None:
        choose_all(auth_client, sample)

        found = products_at(auth_client, sample.size.id, brand_q="Zuzu")

        assert [p["name"] for p in found["products"]] == ["Lapte Zuzu 3.5% 1 l"]

    def test_brand_search_keeps_the_true_cheapest_as_generic(
        self, auth_client: TestClient, sample: Any
    ) -> None:
        choose_all(auth_client, sample)

        found = products_at(auth_client, sample.size.id, brand_q="Zuzu")

        assert found["generic"]["price"] == "7.90"

    def test_brand_search_finds_a_product_with_no_brand(
        self, auth_client: TestClient, db: Session, sample: Any, tree: Tree
    ) -> None:
        choose_all(auth_client, sample)
        add_product(db, sample.stores[1], tree, "Lapte Zuzu 2 l", search_text="lapte zuzu 2 l")

        found = products_at(auth_client, tree.sizes[0].id, brand_q="ZUZU")

        assert [p["name"] for p in found["products"]] == ["Lapte Zuzu 2 l"]

    def test_an_unknown_category_gives_404(self, auth_client: TestClient) -> None:
        assert auth_client.get("/api/categories/-1/products").status_code == 404

    def test_a_category_above_size_level_gives_404(
        self, auth_client: TestClient, sample: Any
    ) -> None:
        assert auth_client.get(f"/api/categories/{sample.type.id}/products").status_code == 404


class TestSearch:
    @pytest.fixture
    def selected(self, auth_client: TestClient, sample: Any) -> Any:
        choose_all(auth_client, sample)
        return sample

    def test_finds_a_product_without_its_diacritics(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(
            db,
            selected.stores[0],
            tree,
            "Brânză telemea catalog",
            search_text="branza telemea catalog",
        )

        ids = [result["size_category_id"] for result in search(auth_client, "branza telemea catalog")]

        assert ids == [tree.sizes[0].id]

    def test_finds_a_product_when_the_search_has_diacritics(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(
            db,
            selected.stores[0],
            tree,
            "Brânză telemea catalog",
            search_text="branza telemea catalog",
        )

        assert len(search(auth_client, "Brânză Telemea Catalog")) == 1

    def test_gives_the_full_path(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(db, selected.stores[0], tree, "Produs Cale Catalog")

        result = search(auth_client, "produs cale catalog")[0]

        assert result["path"] == "Grupa Catalog > Categorie Catalog > Tip Catalog > 2 l"

    def test_gives_the_cheapest_option_at_that_size(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(db, selected.stores[0], tree, "Marca Rara Catalog", "9.00")
        add_product(db, selected.stores[1], tree, "Fara Legatura", "3.00")

        result = search(auth_client, "marca rara catalog")[0]

        assert result["generic"]["name"] == "Fara Legatura"

    def test_groups_products_of_one_size(self, auth_client: TestClient, selected: Any) -> None:
        results = [
            result
            for result in search(auth_client, "albalact 3.5%")
            if result["size_category_id"] == selected.size.id
        ]

        assert len(results) == 1

    def test_unselected_stores_never_appear(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(db, selected.stores[0], tree, "Produs Ascuns Catalog")
        select_stores(auth_client, selected.stores[1].id)

        assert search(auth_client, "produs ascuns catalog") == []

    def test_no_selected_stores_finds_nothing(
        self, auth_client: TestClient, selected: Any
    ) -> None:
        select_stores(auth_client)

        assert search(auth_client, "albalact") == []

    def test_a_blank_search_finds_nothing(self, auth_client: TestClient, selected: Any) -> None:
        assert search(auth_client, "   ") == []

    def test_a_percent_sign_is_plain_text(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(db, selected.stores[0], tree, "Lapte 3.5% Catalog")
        add_product(db, selected.stores[0], tree, "Lapte 35 Catalog", size=1)

        results = search(auth_client, "3.5% catalog")

        assert [result["size_category_id"] for result in results] == [tree.sizes[0].id]

    def test_an_underscore_is_plain_text(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(db, selected.stores[0], tree, "Produs Catalogat")

        assert search(auth_client, "produs_catalogat") == []

    def test_names_starting_with_the_search_come_first(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(db, selected.stores[0], tree, "Ciocolata cu zmeurica", "1.00", size=1)
        add_product(db, selected.stores[0], tree, "Zmeurica proaspata", "9.00")

        results = search(auth_client, "zmeurica")

        assert results[0]["size_category_id"] == tree.sizes[0].id

    def test_equal_matches_go_from_cheapest_to_dearest(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        add_product(db, selected.stores[0], tree, "Ceva zmeurica mare", "9.00")
        add_product(db, selected.stores[0], tree, "Ceva zmeurica mica", "2.00", size=1)

        results = search(auth_client, "zmeurica")

        assert results[0]["size_category_id"] == tree.sizes[1].id

    def test_gives_at_most_50_results(
        self, auth_client: TestClient, db: Session, selected: Any, tree: Tree
    ) -> None:
        for number in range(51):
            size = Category(
                parent_id=tree.type.id,
                name=f"{number + 1} kg",
                level="size",
                size_amount=Decimal(number + 1),
                size_unit="kg",
            )
            db.add(size)
            db.flush()
            db.add(
                StoreProduct(
                    store_id=selected.stores[0].id,
                    size_category_id=size.id,
                    type_category_id=tree.type.id,
                    name=f"Limita Catalog {number}",
                    price=Decimal("1"),
                    unit="kg",
                    search_text=f"limita catalog {number}",
                )
            )
        db.flush()

        assert len(search(auth_client, "limita catalog")) == 50
