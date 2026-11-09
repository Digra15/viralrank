"""Backend routes aggregator — join auth, admin, core."""
from __future__ import annotations

from fastapi import APIRouter

from backend.routes_auth import router as auth_router
from backend.routes_admin import router as admin_router
from backend.app import app as main_app  # existing routes

# Collect routes from main_app
api_router = APIRouter(prefix="/api")

# Import core routes explicitly
from backend.app import (
    api_ads, api_filters, api_fastmoss_rank, api_tiktok_products, api_tiktok_orders,
    api_snapshots, api_ai_analyze, api_ai_models
)

# Register core routes
api_router.get("/ads")(api_ads)
api_router.get("/filters")(api_filters)
api_router.get("/fastmoss/rank/topSelling")(api_fastmoss_rank)
api_router.get("/tiktok/shop/products")(api_tiktok_products)
api_router.get("/tiktok/shop/orders")(api_tiktok_orders)
api_router.get("/snapshots")(api_snapshots)
api_router.post("/ai/analyze")(api_ai_analyze)
api_router.get("/ai/models")(api_ai_models)

# Register auth and admin
api_router.include_router(auth_router)
api_router.include_router(admin_router)

# Mount app on / for index.html
app = main_app
app.include_router(api_router)
