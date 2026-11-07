"""Directions and the shopping route: geo.py and the two routes in plans/router.py."""

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Store, StoreLocation
from app.plans import geo

# A line of points going east from the user, along one latitude.
# 0.01 degrees of longitude at 45.8° N is about 0.78 km.
USER = (45.8, 24.0)


def location(store_id: int, address: str, lat: float, lng: float) -> StoreLocation:
    return StoreLocation(store_id=store_id, address=address, latitude=lat, longitude=lng)


def add_store(db: Session, name: str, *points: tuple[str, float, float]) -> Store:
    store = Store(name=name, colour="#123456")
    db.add(store)
    db.flush()
    for address, lat, lng in points:
        db.add(location(store.id, address, lat, lng))
    db.flush()
    return store


def query(url: str) -> dict[str, list[str]]:
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://www.google.com/maps/dir/"
    return parse_qs(parts.query)


# geo.py


def test_haversine_is_zero_for_the_same_point() -> None:
    assert geo.haversine_km(45.8, 24.0, 45.8, 24.0) == 0


def test_haversine_matches_a_known_distance() -> None:
    # Sibiu to Bucharest centre is about 215 km in a straight line.
    assert geo.haversine_km(45.7983, 24.1256, 44.4268, 26.1025) == pytest.approx(215, abs=5)


def test_nearest_picks_the_closest_location() -> None:
    far = location(1, "far", 45.8, 24.5)
    near = location(1, "near", 45.8, 24.01)
    assert geo.nearest([far, near], *USER) is near


def test_nearest_needs_at_least_one_location() -> None:
    with pytest.raises(ValueError):
        geo.nearest([], *USER)


def test_best_route_visits_the_closer_store_first() -> None:
    near = location(1, "near", 45.8, 24.01)
    far = location(2, "far", 45.8, 24.1)
    assert geo.best_route([[far], [near]], USER) == [near, far]


def test_best_route_chooses_the_branch_that_keeps_the_trip_short() -> None:
    # Store 1's branch on the user's side is best, not the one beside store 2.
    first_beside_user = location(1, "beside user", 45.8, 24.01)
    first_far_side = location(1, "far side", 45.8, 24.3)
    second = location(2, "second", 45.8, 24.05)
    route = geo.best_route([[first_far_side, first_beside_user], [second]], USER)
    assert route == [first_beside_user, second]


def test_best_route_without_a_start_still_orders_the_stops_shortest() -> None:
    a = location(1, "a", 45.8, 24.0)
    b = location(2, "b", 45.8, 24.1)
    c = location(3, "c", 45.8, 24.05)
    route = geo.best_route([[a], [b], [c]], None)
    assert route in ([a, c, b], [b, c, a])


def test_maps_url_with_a_start_and_stops() -> None:
    stops = [location(1, "a", 45.81, 24.01), location(2, "b", 45.82, 24.02)]
    params = query(geo.maps_url(stops, USER))
    assert params["api"] == ["1"]
    assert params["origin"] == ["45.8,24.0"]
    assert params["waypoints"] == ["45.81,24.01"]
    assert params["destination"] == ["45.82,24.02"]
    assert params["travelmode"] == ["driving"]


def test_maps_url_without_a_start_lets_google_use_the_phone_position() -> None:
    params = query(geo.maps_url([location(1, "a", 45.81, 24.01)], None))
    assert "origin" not in params
    assert "waypoints" not in params
    assert params["destination"] == ["45.81,24.01"]


def test_maps_url_separates_several_waypoints_with_a_bar() -> None:
    stops = [location(i, str(i), 45.8, 24.0 + i / 100) for i in range(1, 4)]
    params = query(geo.maps_url(stops, None))
    assert params["waypoints"] == ["45.8,24.01|45.8,24.02"]


# GET /stores/{id}/directions


def test_directions_go_to_the_nearest_branch(auth_client: TestClient, db: Session) -> None:
    store = add_store(db, "Route Shop", ("far", 45.8, 24.5), ("near", 45.8, 24.01))
    response = auth_client.get(
        f"/api/stores/{store.id}/directions", params={"lat": USER[0], "lng": USER[1]}
    )
    assert response.status_code == 200
    assert response.json() == {
        "address": "near",
        "maps_url": "https://www.google.com/maps/dir/?api=1&destination=45.8,24.01",
    }


def test_directions_without_a_position_use_the_first_branch(
    auth_client: TestClient, db: Session
) -> None:
    store = add_store(db, "Route Shop", ("first", 45.8, 24.5), ("second", 45.8, 24.01))
    response = auth_client.get(f"/api/stores/{store.id}/directions")
    assert response.status_code == 200
    assert response.json()["address"] == "first"


def test_directions_for_an_unknown_store_give_404(auth_client: TestClient) -> None:
    assert auth_client.get("/api/stores/999999999/directions").status_code == 404


def test_directions_for_a_store_without_branches_give_404(
    auth_client: TestClient, db: Session
) -> None:
    store = add_store(db, "Route Shop")
    assert auth_client.get(f"/api/stores/{store.id}/directions").status_code == 404


def test_directions_need_both_coordinates(auth_client: TestClient, db: Session) -> None:
    store = add_store(db, "Route Shop", ("a", 45.8, 24.01))
    response = auth_client.get(f"/api/stores/{store.id}/directions", params={"lat": 45.8})
    assert response.status_code == 422


def test_directions_need_a_login(client: TestClient) -> None:
    assert client.get("/api/stores/1/directions").status_code == 401


# GET /stores/route


def route(client: TestClient, store_ids: list[int], position: tuple[float, float] | None = USER):
    params: dict = {"store_ids": store_ids}
    if position:
        params.update(lat=position[0], lng=position[1])
    return client.get("/api/stores/route", params=params)


def test_route_orders_the_stores_and_builds_one_link(
    auth_client: TestClient, db: Session
) -> None:
    far = add_store(db, "Route Far", ("far street", 45.8, 24.1))
    near = add_store(db, "Route Near", ("near street", 45.8, 24.01))

    response = route(auth_client, [far.id, near.id])

    assert response.status_code == 200
    body = response.json()
    assert [stop["store_id"] for stop in body["stops"]] == [near.id, far.id]
    first, second = body["stops"]
    assert first == {
        "store_id": near.id,
        "store_name": "Route Near",
        "address": "near street",
        "lat": 45.8,
        "lng": 24.01,
        "km": pytest.approx(0.8, abs=0.05),
    }
    assert second["km"] == pytest.approx(7.0, abs=0.1)
    assert body["total_km"] == pytest.approx(first["km"] + second["km"], abs=0.05)
    params = query(body["maps_url"])
    assert params["origin"] == ["45.8,24.0"]
    assert params["waypoints"] == ["45.8,24.01"]
    assert params["destination"] == ["45.8,24.1"]


def test_route_without_a_position_has_no_first_leg(auth_client: TestClient, db: Session) -> None:
    one = add_store(db, "Route One", ("one", 45.8, 24.01))
    two = add_store(db, "Route Two", ("two", 45.8, 24.1))

    response = route(auth_client, [one.id, two.id], position=None)

    assert response.status_code == 200
    body = response.json()
    assert body["stops"][0]["km"] is None
    assert body["stops"][1]["km"] == pytest.approx(7.0, abs=0.1)
    assert body["total_km"] == pytest.approx(7.0, abs=0.1)
    assert "origin" not in query(body["maps_url"])


def test_route_counts_a_repeated_store_once(auth_client: TestClient, db: Session) -> None:
    store = add_store(db, "Route One", ("one", 45.8, 24.01))
    body = route(auth_client, [store.id, store.id]).json()
    assert [stop["store_id"] for stop in body["stops"]] == [store.id]


def test_route_with_an_unknown_store_gives_404(auth_client: TestClient, db: Session) -> None:
    store = add_store(db, "Route One", ("one", 45.8, 24.01))
    assert route(auth_client, [store.id, 999999999]).status_code == 404


def test_route_with_a_store_without_branches_gives_404(
    auth_client: TestClient, db: Session
) -> None:
    store = add_store(db, "Route None")
    assert route(auth_client, [store.id]).status_code == 404


def test_route_needs_at_least_one_store(auth_client: TestClient) -> None:
    assert auth_client.get("/api/stores/route", params={"lat": 45.8, "lng": 24.0}).status_code == 422


def test_route_refuses_more_stops_than_google_maps_takes(
    auth_client: TestClient, db: Session
) -> None:
    ids = [
        add_store(db, f"Route Many {i}", (str(i), 45.8, 24.0 + i / 100)).id
        for i in range(geo.MAX_STOPS + 1)
    ]
    assert route(auth_client, ids).status_code == 422


def test_route_needs_a_login(client: TestClient) -> None:
    assert client.get("/api/stores/route", params={"store_ids": [1]}).status_code == 401
