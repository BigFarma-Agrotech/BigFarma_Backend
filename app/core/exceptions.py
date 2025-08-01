"""
Custom exception classes for the application.
"""
from typing import Any, Dict, Optional


class CustomException(Exception):
    """Base custom exception class."""
    
    def __init__(
        self,
        detail: str,
        status_code: int = 500,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.detail = detail
        self.status_code = status_code
        self.headers = headers
        super().__init__(detail)


class ValidationError(CustomException):
    """Validation error exception."""
    
    def __init__(self, detail: str, field: Optional[str] = None):
        self.field = field
        super().__init__(detail=detail, status_code=422)


class AuthenticationError(CustomException):
    """Authentication error exception."""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(detail=detail, status_code=401)


class AuthorizationError(CustomException):
    """Authorization error exception."""
    
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail=detail, status_code=403)


class NotFoundError(CustomException):
    """Not found error exception."""
    
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail=detail, status_code=404)


class ConflictError(CustomException):
    """Conflict error exception."""
    
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(detail=detail, status_code=409)


class RateLimitError(CustomException):
    """Rate limit error exception."""
    
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(detail=detail, status_code=429)


class ExternalServiceError(CustomException):
    """External service error exception."""
    
    def __init__(self, detail: str = "External service error"):
        super().__init__(detail=detail, status_code=502)


class DatabaseError(CustomException):
    """Database error exception."""
    
    def __init__(self, detail: str = "Database error"):
        super().__init__(detail=detail, status_code=500) 