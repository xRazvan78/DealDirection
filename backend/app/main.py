"""FastAPI entry point. Every router is mounted here under /api.

Add routes in the unit's own router.py, not in this file.
"""

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.auth.router import router as auth_router
from app.cards.router import router as cards_router
from app.catalog.router import router as catalog_router
from app.imports.router import router as imports_router
from app.init_db import init_db
from app.lists.router import router as lists_router
from app.plans.router import router as plans_router
from app.receipts.router import router as receipts_router
from app.wallet.router import router as wallet_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="DealDirection", lifespan=lifespan)

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


for router in (
    auth_router,
    catalog_router,
    lists_router,
    plans_router,
    receipts_router,
    imports_router,
    wallet_router,
    cards_router,
):
    api.include_router(router)

app.include_router(api)


def add_frontend_routes(target: FastAPI, dist: Path) -> None:
    """Serve the built Angular app, with index.html for its client-side routes.

    Call this after every API route, because it catches all remaining paths.
    """
    root = dist.resolve()

    @target.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def unknown_api(path: str) -> None:
        raise HTTPException(status_code=404)

    @target.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        requested = (root / path).resolve()
        if requested.is_file() and requested.is_relative_to(root):
            return FileResponse(requested)

        index = root / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(index)


add_frontend_routes(app, Path(__file__).parents[2] / "frontend" / "dist" / "frontend" / "browser")
