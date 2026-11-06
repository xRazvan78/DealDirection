"""FastAPI entry point. Every router is mounted here under /api.

Add routes in the unit's own router.py, not in this file.
"""

from fastapi import APIRouter, FastAPI

from app.auth.router import router as auth_router
from app.cards.router import router as cards_router
from app.catalog.router import router as catalog_router
from app.imports.router import router as imports_router
from app.lists.router import router as lists_router
from app.plans.router import router as plans_router
from app.receipts.router import router as receipts_router
from app.wallet.router import router as wallet_router

app = FastAPI(title="DealDirection")

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

# Task 14: serve frontend/dist/frontend/browser here, after the API routes,
# and return index.html for unknown non-API paths.
