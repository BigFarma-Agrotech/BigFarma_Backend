from fastapi import APIRouter

from app.api.v1.endpoints import auth, profile

api_router = APIRouter()

# Include auth routes
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Include profile routes
api_router.include_router(profile.router, prefix="/profile", tags=["profile"]) 