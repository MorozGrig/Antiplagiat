"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1.endpoints.materials import router as materials_router

api_router = APIRouter()
api_router.include_router(materials_router)

# Alias retained for applications that conventionally import 'router'.
router = api_router
