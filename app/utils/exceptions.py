from fastapi import HTTPException, status


class CustomException(HTTPException):
    """Base custom exception class."""
    
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class AuthenticationError(CustomException):
    """Raised when authentication fails."""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(CustomException):
    """Raised when user is not authorized to perform an action."""
    
    def __init__(self, detail: str = "Not authorized"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)


class UserNotFoundError(CustomException):
    """Raised when a user is not found."""
    
    def __init__(self, detail: str = "User not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class UserAlreadyExistsError(CustomException):
    """Raised when trying to create a user that already exists."""
    
    def __init__(self, detail: str = "User already exists"):
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)


class InvalidOTPError(CustomException):
    """Raised when OTP validation fails."""
    
    def __init__(self, detail: str = "Invalid OTP"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class OTPExpiredError(CustomException):
    """Raised when OTP has expired."""
    
    def __init__(self, detail: str = "OTP has expired"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class InvalidCredentialsError(CustomException):
    """Raised when login credentials are invalid."""
    
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class TokenExpiredError(CustomException):
    """Raised when JWT token has expired."""
    
    def __init__(self, detail: str = "Token has expired"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class InvalidTokenError(CustomException):
    """Raised when JWT token is invalid."""
    
    def __init__(self, detail: str = "Invalid token"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class ValidationError(CustomException):
    """Raised when data validation fails."""
    
    def __init__(self, detail: str = "Validation error"):
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class DatabaseError(CustomException):
    """Raised when database operations fail."""
    
    def __init__(self, detail: str = "Database error"):
        super().__init__(detail=detail, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmailError(CustomException):
    """Raised when email operations fail."""
    
    def __init__(self, detail: str = "Email error"):
        super().__init__(detail=detail, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RateLimitError(CustomException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(detail=detail, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


class ServiceUnavailableError(CustomException):
    """Raised when a service is unavailable."""
    
    def __init__(self, detail: str = "Service unavailable"):
        super().__init__(detail=detail, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


# Exception handlers mapping
EXCEPTION_HANDLERS = {
    AuthenticationError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    AuthorizationError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    UserNotFoundError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    UserAlreadyExistsError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    InvalidOTPError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    OTPExpiredError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    InvalidCredentialsError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    TokenExpiredError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    InvalidTokenError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    ValidationError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    DatabaseError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    EmailError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    RateLimitError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
    ServiceUnavailableError: lambda exc: {"detail": exc.detail, "status_code": exc.status_code},
} 