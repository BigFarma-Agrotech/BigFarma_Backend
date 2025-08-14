import logging
import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

from app.services.auth import auth_service, get_db
from app.database import User, Profile
from app.schemas.accounts import (
    UserCreate, UserLogin, UserResponse, AuthResponse, TokenResponse,
    OTPRequest, OTPVerify, OTPResponse, MessageResponse, UserUpdate,
    ProfileCreate, ProfileUpdate, ProfileResponse, UserWithProfileResponse,
    PasswordReset, ChangePasswordRequest, ForgotPasswordRequest
)
from app.api.v1.dependencies import get_current_user, get_current_active_user, get_current_verified_user
from app.utils.exceptions import (
    AuthenticationError, UserNotFoundError, InvalidOTPError, 
    UserAlreadyExistsError, InvalidCredentialsError
)
from app.config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate) -> Any:
    """Register a new user with email or phone."""
    try:
        user = await auth_service.create_user(user_data)
        
        access_token = auth_service.create_access_token(
            data={
                "sub": user["id"],
                "email": user.get("email"),
                "phone": user.get("phone"),
            }
        )

        profile = await auth_service.get_user_profile(user["id"])

        user_response = UserWithProfileResponse(
            id=user["id"],
            email=user.get("email"),
            phone=user.get("phone"),
        )

        return {
            "message": "User registered successfully. Please complete your profile setup.",
            "user": user_response,
        }

    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in user registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )



@router.post("/login", response_model=AuthResponse)
async def login(user_data: UserLogin) -> Any:
    """Login user with email/phone and password."""
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(user_data)
        if not user:
            raise InvalidCredentialsError("Invalid credentials")
        
        # Create access token
        access_token = auth_service.create_access_token(
            data={
                "sub": user["id"],
                "email": user.get("email"),
                "phone": user.get("phone"),
                "category": user["user_category"]
            }
        )
        
        # Get user profile
        profile = await auth_service.get_user_profile(user["id"])
        
        # Prepare response
        user_response = UserWithProfileResponse(
            email=user.get("email"),
            phone=user.get("phone"),
            user_category=user["user_category"],
        )
        
        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        return AuthResponse(user=user_response, token=token_response)
        
    except InvalidCredentialsError:
        raise
    except Exception as e:
        logger.error(f"Error in user login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/request-otp", response_model=OTPResponse)
async def request_otp(otp_data: OTPRequest) -> Any:
    """Request OTP for email/phone verification"""
    try:
        user_exists = await auth_service.check_user_exists(otp_data.email)
        if not user_exists:
            raise UserNotFoundError("User not found")
        
        # Create and send OTP
        otp_code = await auth_service.create_otp(otp_data)
        
        # Send OTP via email if it's an email OTP
        if otp_data.otp_type == "email":
            await auth_service.send_otp_email(otp_data.email, otp_code, "email")
        
        # In development, we'll return the OTP code for testing
        if settings.ENVIRONMENT == "development":
            return OTPResponse(
                message=f"OTP sent successfully. Code: {otp_code}",
                otp_type=otp_data.otp_type
            )
        else:
            return OTPResponse(
                message="OTP sent successfully",
                otp_type=otp_data.otp_type
            )
            
    except (UserNotFoundError, InvalidOTPError):
        raise
    except Exception as e:
        logger.error(f"Error requesting OTP: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/verify-otp", response_model=MessageResponse)
async def verify_otp(otp_data: OTPVerify) -> Any:
    """Verify OTP for email/phone verification."""
    try:
        await auth_service.verify_otp(otp_data)
        return MessageResponse(message="OTP verified successfully")
        
    except (UserNotFoundError, InvalidOTPError):
        raise
    except Exception as e:
        logger.error(f"Error verifying OTP: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/forgot-password", response_model=OTPResponse)
async def forgot_password(request_data: ForgotPasswordRequest) -> Any:
    """Send OTP for password reset (only if user exists)."""
    try:
        # Check if user exists first
        user_exists = await auth_service.check_user_exists(request_data.email)
        if not user_exists:
            raise UserNotFoundError("User not found")
        
        # Create OTP for password reset
        otp_data = OTPRequest(email=request_data.email, otp_type="password_reset")
        otp_code = await auth_service.create_otp(otp_data)
        
        # Send OTP via email
        await auth_service.send_otp_email(request_data.email, otp_code, "password_reset")
        
        # In development, we'll return the OTP code for testing
        if settings.ENVIRONMENT == "development":
            return OTPResponse(
                message=f"Password reset OTP sent successfully. Code: {otp_code}",
                otp_type="password_reset"
            )
        else:
            return OTPResponse(
                message="Password reset OTP sent successfully",
                otp_type="password_reset"
            )
            
    except (UserNotFoundError, InvalidOTPError):
        raise
    except Exception as e:
        logger.error(f"Error in forgot password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(reset_data: PasswordReset) -> Any:
    """Reset password using OTP."""
    try:
        # Verify OTP first
        otp_verify_data = OTPVerify(
            email=reset_data.email,
            otp_code=reset_data.otp_code,
            otp_type="password_reset"
        )
        await auth_service.verify_otp(otp_verify_data)
        
        # Update password
        user = await auth_service.get_user_by_email(reset_data.email)
        if not user:
            raise UserNotFoundError("User not found")
        
        hashed_password = auth_service.get_password_hash(reset_data.new_password)
        
        # Update password using SQLAlchemy
        db = get_db()
        try:
            user_obj = db.query(User).filter(User.id == user["id"]).first()
            if user_obj:
                user_obj.password_hash = hashed_password
                db.commit()
        finally:
            db.close()
        
        return MessageResponse(message="Password reset successfully")
        
    except (UserNotFoundError, InvalidOTPError):
        raise
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/me/profile", response_model=ProfileResponse)
async def update_profile(
    profile_update: ProfileUpdate,
    current_user: dict = Depends(get_current_active_user)
) -> Any:
    """Update user profile."""
    try:
        update_data = profile_update.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data provided for update"
            )
        
        # Update profile using SQLAlchemy
        db = get_db()
        try:
            profile_obj = db.query(Profile).filter(Profile.user_id == current_user["id"]).first()
            if profile_obj:
                for key, value in update_data.items():
                    setattr(profile_obj, key, value)
                db.commit()
                db.refresh(profile_obj)
                
                return ProfileResponse(
                    id=profile_obj.id,
                    user_id=profile_obj.user_id,
                    first_name=profile_obj.first_name,
                    last_name=profile_obj.last_name,
                    avatar_url=profile_obj.avatar_url,
                    bio=profile_obj.bio,
                    date_of_birth=profile_obj.date_of_birth,
                    gender=profile_obj.gender,
                    address=profile_obj.address,
                    city=profile_obj.city,
                    state=profile_obj.state,
                    country=profile_obj.country,
                    postal_code=profile_obj.postal_code,
                    created_at=profile_obj.created_at,
                    updated_at=profile_obj.updated_at
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Profile not found"
                )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_active_user)
) -> Any:
    """Change user password."""
    try:
        # Verify current password
        if not auth_service.verify_password(
            password_data.current_password, 
            current_user["password_hash"]
        ):
            raise InvalidCredentialsError("Current password is incorrect")
        
        # Update password
        hashed_password = auth_service.get_password_hash(password_data.new_password)
        
        # Update password using SQLAlchemy
        db = get_db()
        try:
            user_obj = db.query(User).filter(User.id == current_user["id"]).first()
            if user_obj:
                user_obj.password_hash = hashed_password
                db.commit()
        finally:
            db.close()
        
        return MessageResponse(message="Password changed successfully")
        
    except InvalidCredentialsError:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        ) 