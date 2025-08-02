import logging
import random
import string
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    
    async def check_user_exists(self, email: str) -> bool:
        """Check if a user exists by email (without exposing sensitive data)."""
        db = get_db()
        try:
            user = db.query(User).filter(User.email == email).first()
            return user is not None
        except Exception as e:
            logger.error(f"Error checking if user exists: {e}")
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
            
            # Check for recent OTP requests (rate limiting)
            recent_otp = db.query(OTP).filter(
                OTP.user_id == user.id,
                OTP.otp_type == otp_data.otp_type,
                OTP.created_at >= datetime.utcnow() - timedelta(minutes=1)  # 1 minute cooldown
            ).first()
            
            if recent_otp:
                raise InvalidOTPError("Please wait at least 1 minute before requesting another OTP")
            
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
            
            logger.info(f"OTP created for user: {otp_data.email}, type: {otp_data.otp_type}")
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
            
            # Mark user as verified only for email verification, not password reset
            if otp_data.otp_type != "password_reset":
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
    
    async def send_otp_email(self, email: str, otp_code: str, otp_type: str = "email") -> None:
        """Send OTP code via email."""
        try:
            # Check if SMTP is configured
            if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
                logger.warning("SMTP credentials not configured. OTP code: %s", otp_code)
                return
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USER
            msg['To'] = email
            
            # Set subject and body based on OTP type
            if otp_type == "password_reset":
                msg['Subject'] = "BigFarma - Password Reset OTP"
                body = f"""
                <html>
                <body>
                    <h2>BigFarma Password Reset</h2>
                    <p>You requested a password reset for your BigFarma account.</p>
                    <p>Your password reset code is: <strong style="font-size: 24px; color: #dc3545;">{otp_code}</strong></p>
                    <p>This code will expire in 10 minutes.</p>
                    <p>If you didn't request this password reset, please ignore this email and your password will remain unchanged.</p>
                    <br>
                    <p>Best regards,<br>BigFarma Team</p>
                </body>
                </html>
                """
            else:
                msg['Subject'] = "BigFarma - Email Verification OTP"
                body = f"""
                <html>
                <body>
                    <h2>BigFarma Email Verification</h2>
                    <p>You requested an email verification code for your BigFarma account.</p>
                    <p>Your verification code is: <strong style="font-size: 24px; color: #007bff;">{otp_code}</strong></p>
                    <p>This code will expire in 10 minutes.</p>
                    <p>If you didn't request this code, please ignore this email.</p>
                    <br>
                    <p>Best regards,<br>BigFarma Team</p>
                </body>
                </html>
                """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email with better error handling
            logger.info(f"Attempting to send OTP email to {email} via {settings.SMTP_HOST}:{settings.SMTP_PORT}")
            
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            
            # Login with detailed error handling
            try:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                logger.info("SMTP login successful")
            except smtplib.SMTPAuthenticationError as auth_error:
                logger.error(f"SMTP authentication failed: {auth_error}")
                logger.error("Please check your SMTP credentials. For Gmail, use App Password instead of regular password.")
                server.quit()
                return
            except Exception as login_error:
                logger.error(f"SMTP login error: {login_error}")
                server.quit()
                return
            
            # Send the email
            try:
                text = msg.as_string()
                server.sendmail(settings.SMTP_USER, email, text)
                server.quit()
                logger.info(f"OTP email sent successfully to {email} for {otp_type}")
            except Exception as send_error:
                logger.error(f"Error sending email: {send_error}")
                server.quit()
                return
                
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication error for {email}: {e}")
            logger.error("For Gmail: Use App Password instead of regular password")
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error for {email}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending OTP email to {email}: {e}")
            # Don't raise the exception to avoid breaking the process
            # The OTP is still created and stored in the database


# Create service instance
auth_service = AuthService() 