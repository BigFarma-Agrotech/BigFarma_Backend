"""
Logging configuration.
"""
import logging
import sys
from typing import Any, Dict

from app.core.config import settings


def setup_logging() -> None:
    """Configure logging."""
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def log_request(request_id: str, method: str, url: str, status_code: int, duration: float) -> None:
    """Log HTTP request details."""
    logger = get_logger("http_request")
    logger.info(
        "HTTP request",
        extra={
            "request_id": request_id,
            "method": method,
            "url": url,
            "status_code": status_code,
            "duration": duration,
        }
    )


def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """Log error with context."""
    logger = get_logger("error")
    logger.error(
        "Application error",
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {},
        },
        exc_info=True,
    ) 