from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from features.auth.routes import router as auth_router
from features.users.routes import router as users_router
from features.marketplace.routes import router as marketplace_router
from features.orders.routes import router as orders_router
from features.group_buy.routes import router as group_buy_router
from features.wallet.routes import router as wallet_router
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# debug is deliberately not passed: FastAPI's debug mode sends full Python
# tracebacks (file paths, SQL, parameters) to clients. Errors are logged below.
app = FastAPI(title=settings.APP_NAME)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "https://bigfarma-frontend-w08r.onrender.com",
    "https://big-farma-frontend-omega.vercel.app",
    "https://big-farma-frontend.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(users_router, prefix="/api/v1", tags=["Users"])
app.include_router(marketplace_router, prefix="/api/v1", tags=["Marketplace"])
app.include_router(orders_router, prefix="/api/v1", tags=["Orders"])
app.include_router(group_buy_router, prefix="/api/v1", tags=["Group Buy"])
app.include_router(wallet_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "BigFarma API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "BigFarma API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
