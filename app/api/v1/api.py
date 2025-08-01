"""
Main API router for v1 endpoints.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, health

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"]) 