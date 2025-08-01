import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from .database import create_tables

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.api import api_router
from app.core.exceptions import CustomException

# Initialize structured logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting BigFarma Backend API")
    
    yield
    
    # Shutdown
    logger.info("Shutting down BigFarma Backend API")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="BigFarma Backend API",
        description="A production-ready FastAPI backend for BigFarma with Supabase",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Add routes
    app.include_router(api_router, prefix="/api/v1")

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """Add custom headers and metrics."""
        import time
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

    @app.exception_handler(CustomException)
    async def custom_exception_handler(request: Request, exc: CustomException):
        """Handle custom exceptions."""
        logger.error(
            "Custom exception occurred",
            extra={
                "exception_type": type(exc).__name__,
                "detail": exc.detail,
                "status_code": exc.status_code
            }
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    
    @app.on_event("startup")
    def startup_event():
        create_tables()

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        logger.error(
            "Unhandled exception occurred",
            extra={
                "exception_type": type(exc).__name__,
                "detail": str(exc)
            },
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
    ) 