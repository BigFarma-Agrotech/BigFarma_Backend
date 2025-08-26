from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from database import Base, engine
from api import auth, users, farmers, consumers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="BigFarma Auth API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(farmers.router)
app.include_router(consumers.router)

@app.get("/")
async def root():
    return {"message": "BigFarma Authentication API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)