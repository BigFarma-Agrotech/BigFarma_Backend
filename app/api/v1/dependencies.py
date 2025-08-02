import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth import auth_service
from app.utils.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError
from app.utils.security import verify_token

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current authenticated user from JWT token."""
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if payload is None:
            raise InvalidTokenError("Invalid token")
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise InvalidTokenError("Token missing user ID")
        
        user = await auth_service.get_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found")
        
        if not user["is_active"]:
            raise AuthenticationError("User account is deactivated")
        
        return user
        
    except (InvalidTokenError, AuthenticationError):
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise AuthenticationError("Authentication failed")


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current active user."""
    if not current_user["is_active"]:
        raise AuthenticationError("User account is deactivated")
    return current_user


async def get_current_verified_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current verified user."""
    if not current_user["is_verified"]:
        raise AuthenticationError("User account is not verified")
    return current_user


async def get_current_superuser(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current superuser."""
    if not current_user["is_superuser"]:
        raise AuthenticationError("Not enough permissions")
    return current_user


def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[dict]:
    """Get current user if token is provided, otherwise return None."""
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if payload is None:
            return None
        
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        return {"id": user_id}
        
    except Exception:
        return None 