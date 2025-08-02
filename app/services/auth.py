import logging
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config.config import settings
from app.database import SessionLocal, User, OTP, Profile
from app.schemas.accounts import UserCreate, UserLogin, OTPRequest, OTPVerify
from app.utils.exceptions import (
    AuthenticationError, 
    UserNotFoundError, 
    InvalidOTPError, 
    UserAlreadyExistsError
)

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


class AuthService:
    """Authentication service for user management and OTP handling."""
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            return None
    
    def generate_otp(self, length: int = 6) -> str:
        """Generate a random OTP code."""
        return ''.join(random.choices(string.digits, k=length))
    
    async def create_user(self, user_data: UserCreate) -> Dict[str, Any]:
        """Create a new user."""
        db = get_db()
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == user_data.email).first()
            if existing_user:
                raise UserAlreadyExistsError("User with this email already exists")
            
            # Hash password
            hashed_password = self.get_password_hash(user_data.password)
            
            # Create user
            user = User(
                id=str(uuid.uuid4()),
                email=user_data.email,
                phone=user_data.phone,
                password_hash=hashed_password,
                is_active=True,
                is_verified=False,
                is_superuser=False
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            logger.info(f"User created successfully: {user.email}")
            return {
                "id": user.id,
                "email": user.email,
                "phone": user.phone,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "is_superuser": user.is_superuser,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            }
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            raise
        finally:
            db.close()
    
    async def authenticate_user(self, user_data: UserLogin) -> Optional[Dict[str, Any]]:
        """Authenticate a user with email and password."""
        db = get_db()
        try:
            user = db.query(User).filter(User.email == user_data.email).first()
            if not user:
                return None
            
            if not self.verify_password(user_data.password, user.password_hash):
                return None
            
            if not user.is_active:
                raise AuthenticationError("User account is deactivated")
            
            return {
                "id": user.id,
                "email": user.email,
                "phone": user.phone,
                "password_hash": user.password_hash,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "is_superuser": user.is_superuser,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            }
            
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            raise
        finally:
            db.close()
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        db = get_db()
        try:
            user = db.query(User).filter(User.email == email).first()
            if user:
                return {
                    "id": user.id,
                    "email": user.email,
                    "phone": user.phone,
                    "password_hash": user.password_hash,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "is_superuser": user.is_superuser,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            raise
        finally:
            db.close()
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        db = get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return {
                    "id": user.id,
                    "email": user.email,
                    "phone": user.phone,
                    "password_hash": user.password_hash,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "is_superuser": user.is_superuser,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            raise
        finally:
            db.close()
    
    async def create_otp(self, otp_data: OTPRequest) -> str:
        """Create and store an OTP for user verification."""
        db = get_db()
        try:
            user = db.query(User).filter(User.email == otp_data.email).first()
            if not user:
                raise UserNotFoundError("User not found")
            
            # Generate OTP
            otp_code = self.generate_otp()
            expires_at = datetime.utcnow() + timedelta(minutes=10)  # OTP expires in 10 minutes
            
            # Store OTP in database
            otp = OTP(
                id=str(uuid.uuid4()),
                user_id=user.id,
                otp_code=otp_code,
                otp_type=otp_data.otp_type,
                expires_at=expires_at,
                is_used=False
            )
            
            db.add(otp)
            db.commit()
            
            logger.info(f"OTP created for user: {otp_data.email}")
            return otp_code
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating OTP: {e}")
            raise
        finally:
            db.close()
    
    async def verify_otp(self, otp_data: OTPVerify) -> bool:
        """Verify an OTP code."""
        db = get_db()
        try:
            user = db.query(User).filter(User.email == otp_data.email).first()
            if not user:
                raise UserNotFoundError("User not found")
            
            # Get the most recent unused OTP for this user
            otp = db.query(OTP).filter(
                OTP.user_id == user.id,
                OTP.otp_type == otp_data.otp_type,
                OTP.is_used == False
            ).order_by(OTP.created_at.desc()).first()
            
            if not otp:
                raise InvalidOTPError("No valid OTP found")
            
            # Check if OTP is expired
            if datetime.utcnow() > otp.expires_at:
                raise InvalidOTPError("OTP has expired")
            
            # Check if OTP code matches
            if otp.otp_code != otp_data.otp_code:
                raise InvalidOTPError("Invalid OTP code")
            
            # Mark OTP as used
            otp.is_used = True
            db.commit()
            
            # Mark user as verified
            user.is_verified = True
            db.commit()
            
            logger.info(f"OTP verified successfully for user: {otp_data.email}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error verifying OTP: {e}")
            raise
        finally:
            db.close()
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile information."""
        db = get_db()
        try:
            profile = db.query(Profile).filter(Profile.user_id == user_id).first()
            if profile:
                return {
                    "id": profile.id,
                    "user_id": profile.user_id,
                    "first_name": profile.first_name,
                    "last_name": profile.last_name,
                    "avatar_url": profile.avatar_url,
                    "bio": profile.bio,
                    "date_of_birth": profile.date_of_birth,
                    "gender": profile.gender,
                    "address": profile.address,
                    "city": profile.city,
                    "state": profile.state,
                    "country": profile.country,
                    "postal_code": profile.postal_code,
                    "created_at": profile.created_at,
                    "updated_at": profile.updated_at
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            raise
        finally:
            db.close()


# Create service instance
auth_service = AuthService() 