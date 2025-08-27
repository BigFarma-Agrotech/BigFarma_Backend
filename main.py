from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from config import settings

from database import Base, engine
from features.auth.routes import router as auth_router
from features.users.routes import router as users_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

app = app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include feature routers
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(users_router, prefix="/api/v1", tags=["Users"])

@app.get("/")
async def root():
    return {"message": "BigFarma API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "BigFarma API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)