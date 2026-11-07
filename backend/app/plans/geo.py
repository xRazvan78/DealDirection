"""Distances, the nearest branch, the best shopping route and Google Maps links. Owner: Member 2, Task 9.

The route part was added by Member 3. Distances are straight lines (haversine),
which is enough to order 2–4 stores in one town. Google Maps works out the real
roads once the link is opened, so no API key is needed.
"""

from collections.abc import Sequence
from itertools import permutations
from math import asin, cos, radians, sin, sqrt
from typing import Protocol
from urllib.parse import urlencode

EARTH_RADIUS_KM = 6371.0

# Google Maps links take up to 3 waypoints on phone browsers, plus the destination.
MAX_STOPS = 4

MAPS_DIRECTIONS = "https://www.google.com/maps/dir/"

Point = tuple[float, float]


class Place(Protocol):
    latitude: float
    longitude: float


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """The straight-line distance between two points, in kilometres."""
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def distance_km(start: Point, place: Place) -> float:
    return haversine_km(start[0], start[1], place.latitude, place.longitude)


def point(place: Place) -> Point:
    return (place.latitude, place.longitude)


def nearest[P: Place](locations: Sequence[P], lat: float, lng: float) -> P:
    """The location closest to (lat, lng). Raises ValueError when there are none."""
    if not locations:
        raise ValueError("No locations to choose from")
    return min(locations, key=lambda place: distance_km((lat, lng), place))


def _best_branches[P: Place](
    stores: Sequence[Sequence[P]], start: Point | None
) -> tuple[float, list[P]]:
    """The shortest trip through the stores in this order, choosing one branch of each.

    Each step only depends on the branch before it, so keeping the best trip
    ending at each branch gives the exact answer.
    """
    best: list[tuple[float, list[P]]] = [
        (distance_km(start, branch) if start else 0.0, [branch]) for branch in stores[0]
    ]
    for branches in stores[1:]:
        best = [
            min(
                ((km + distance_km(point(trip[-1]), branch), [*trip, branch]) for km, trip in best),
                key=lambda option: option[0],
            )
            for branch in branches
        ]
    return min(best, key=lambda option: option[0])


def best_route[P: Place](stores: Sequence[Sequence[P]], start: Point | None) -> list[P]:
    """One branch of each store, in the order that makes the shortest trip.

    `stores` holds each store's branches, and every store needs at least one.
    Without a start the trip begins at whichever stop makes it shortest.
    """
    trips = (_best_branches(order, start) for order in permutations(stores))
    return min(trips, key=lambda option: option[0])[1]


def _coordinates(place: Place) -> str:
    return f"{place.latitude},{place.longitude}"


def maps_url(stops: Sequence[Place], start: Point | None, mode: str | None = "driving") -> str:
    """A Google Maps directions link through the stops in order, ending at the last.

    Without a start, Google Maps begins at the phone's own position.
    """
    params: dict[str, str] = {"api": "1"}
    if start:
        params["origin"] = f"{start[0]},{start[1]}"
    params["destination"] = _coordinates(stops[-1])
    if len(stops) > 1:
        params["waypoints"] = "|".join(_coordinates(stop) for stop in stops[:-1])
    if mode:
        params["travelmode"] = mode
    return f"{MAPS_DIRECTIONS}?{urlencode(params, safe=',')}"
