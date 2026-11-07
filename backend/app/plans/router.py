"""Plans, the one-time suggestion, activation and directions. Owner: Member 2, Task 9.

The directions and shopping-route routes were added by Member 3. Plans,
the suggestion and activation are still Task 9's.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Store, StoreLocation, User
from app.plans import geo

router = APIRouter(tags=["plans"])

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
Latitude = Annotated[float | None, Query(ge=-90, le=90)]
Longitude = Annotated[float | None, Query(ge=-180, le=180)]


class DirectionsOut(BaseModel):
    address: str
    maps_url: str


class RouteStop(BaseModel):
    store_id: int
    store_name: str
    address: str
    lat: float
    lng: float
    km: float | None
    """Straight-line distance from the stop before, or from the user. None for a first stop with no start."""


class RouteOut(BaseModel):
    stops: list[RouteStop]
    total_km: float
    maps_url: str


def _start(lat: float | None, lng: float | None) -> geo.Point | None:
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Send both lat and lng, or neither")
    return None if lat is None or lng is None else (lat, lng)


def _branches(db: Session, store_id: int) -> list[StoreLocation]:
    """The store's branches, oldest first. 404 for an unknown store or one with none."""
    if db.get(Store, store_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Store {store_id} not found")
    branches = list(
        db.scalars(
            select(StoreLocation)
            .where(StoreLocation.store_id == store_id)
            .order_by(StoreLocation.id)
        )
    )
    if not branches:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Store {store_id} has no address yet")
    return branches


# Declared before /stores/{store_id}/... so "route" is never read as a store id.
@router.get("/stores/route")
def shopping_route(
    store_ids: Annotated[list[int], Query(min_length=1)],
    db: Db,
    user: CurrentUser,
    lat: Latitude = None,
    lng: Longitude = None,
) -> RouteOut:
    """The order to visit these stores in, one branch each, and one Google Maps link for the trip."""
    start = _start(lat, lng)
    unique_ids = list(dict.fromkeys(store_ids))
    if len(unique_ids) > geo.MAX_STOPS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"A route can have at most {geo.MAX_STOPS} stores",
        )

    stops = geo.best_route([_branches(db, store_id) for store_id in unique_ids], start)

    out: list[RouteStop] = []
    previous = start
    total = 0.0
    for stop in stops:
        km = geo.distance_km(previous, stop) if previous else None
        total += km or 0.0
        out.append(
            RouteStop(
                store_id=stop.store_id,
                store_name=db.get_one(Store, stop.store_id).name,
                address=stop.address,
                lat=stop.latitude,
                lng=stop.longitude,
                km=None if km is None else round(km, 1),
            )
        )
        previous = geo.point(stop)
    return RouteOut(stops=out, total_km=round(total, 1), maps_url=geo.maps_url(stops, start))


@router.get("/stores/{store_id}/directions")
def directions(
    store_id: int, db: Db, user: CurrentUser, lat: Latitude = None, lng: Longitude = None
) -> DirectionsOut:
    """A Google Maps link to the store's branch nearest the user, or its first branch."""
    start = _start(lat, lng)
    branches = _branches(db, store_id)
    branch = geo.nearest(branches, *start) if start else branches[0]
    return DirectionsOut(address=branch.address, maps_url=geo.maps_url([branch], None, mode=None))
