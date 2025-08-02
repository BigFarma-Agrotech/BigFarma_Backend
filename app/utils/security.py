import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)  # Refresh token expires in 7 days
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None


def is_token_expired(token: str) -> bool:
    """Check if a token is expired."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        if exp is None:
            return True
        
        return datetime.utcnow() > datetime.fromtimestamp(exp)
    except JWTError:
        return True


def get_token_payload(token: str) -> Optional[Dict[str, Any]]:
    """Get token payload without verification (for debugging)."""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except JWTError as e:
        logger.error(f"Error getting token payload: {e}")
        return None


def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token."""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for storage."""
    import hashlib
    return hashlib.sha256(data.encode()).hexdigest()


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength and return detailed feedback."""
    import re
    
    errors = []
    warnings = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    elif len(password) < 12:
        warnings.append("Consider using a longer password (12+ characters)")
    
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        warnings.append("Consider adding special characters for better security")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "score": max(0, 10 - len(errors) * 2 - len(warnings))
    } 