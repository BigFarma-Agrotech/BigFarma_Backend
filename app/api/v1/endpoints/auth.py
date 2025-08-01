"""
Authentication endpoints based on user stories.
"""
from datetime import timedelta
from typing import Dict, Any, Optional
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, validator

from app.core.supabase import supabase
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    generate_password_reset_token,
    verify_password_reset_token,
)
from app.core.config import settings
from app.core.exceptions import AuthenticationError, ValidationError
from app.schemas.auth import Token, UserCreate, UserLogin, PasswordReset, PasswordResetConfirm

router = APIRouter()


class SignUpRequest(BaseModel):
    """Sign up request model based on user story."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(..., min_length=1)
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'\d', v):
            raise ValueError("Password must contain at least one number")
        return v
    
    @validator('confirm_password')
    def validate_confirm_password(cls, v, values):
        """Validate password confirmation."""
        if 'password' in values and v != values['password']:
            raise ValueError("Passwords do not match")
        return v


class SignInRequest(BaseModel):
    """Sign in request model."""
    email: EmailStr
    password: str


class OTPVerificationRequest(BaseModel):
    """OTP verification request model."""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


@router.post("/signup", response_model=Dict[str, Any])
async def signup(user_data: SignUpRequest) -> Dict[str, Any]:
    """
    User signup endpoint based on user story.
    
    Requirements:
    - Email validation
    - Password validation (8+ chars, lowercase, uppercase, numbers)
    - Full name and address required
    - Email verification OTP
    """
    # Check if user already exists by email
    existing_user = await supabase.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email address you entered is already registered. Please use a different email address"
        )
    
    # Create user data for Supabase
    user_data_dict = {
        "email": user_data.email,
        "hashed_password": get_password_hash(user_data.password),
        "full_name": user_data.full_name,
        "address": user_data.address,
        "is_active": False,  # User needs to verify email first
        "email_verified": False,
    }
    
    try:
        # Create user in Supabase
        user = await supabase.create_user(user_data_dict)
        
        # Generate and send OTP (in production, this would send an email)
        otp = "123456"  # In production, generate a real OTP
        # Store OTP in database with expiration (30 minutes)
        
        return {
            "message": "Account created successfully. Please check your email for verification OTP.",
            "user_id": user["id"],
            "email": user_data.email,
            "requires_verification": True
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account. Please try again."
        )


@router.post("/verify-email", response_model=Dict[str, Any])
async def verify_email(verification_data: OTPVerificationRequest) -> Dict[str, Any]:
    """
    Email verification endpoint.
    
    Requirements:
    - OTP verification
    - 30-minute expiration
    - Activate account after verification
    """
    # In production, verify OTP from database
    # For now, we'll accept any 6-digit code
    if verification_data.otp != "123456":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP. Please check your email and try again."
        )
    
    # Get user by email
    user = await supabase.get_user_by_email(verification_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user to verified
    updated_user = await supabase.update_user(user["id"], {
        "email_verified": True,
        "is_active": True
    })
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(updated_user["id"])},
        expires_delta=access_token_expires
    )
    
    return {
        "message": "Email verified successfully! Your account is now active.",
        "user_id": updated_user["id"],
        "email_verified": True,
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/signin", response_model=Token)
async def signin(signin_data: SignInRequest) -> Token:
    """
    User signin endpoint.
    
    Requirements:
    - Email validation
    - Password validation
    - Handle unverified accounts
    """
    # Find user by email
    user = await supabase.get_user_by_email(signin_data.email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if email is verified
    if not user.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please verify your email before signing in. Check your email for verification OTP."
        )
    
    # Verify password
    if not verify_password(signin_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is deactivated. Please contact support."
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["id"])},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/forgot-password")
async def forgot_password(password_reset: PasswordReset) -> Dict[str, str]:
    """
    Forgot password endpoint.
    
    Requirements:
    - Send OTP to registered email
    - 1-minute expiration for OTP
    """
    user = await supabase.get_user_by_email(password_reset.email)
    
    if user:
        # Generate reset token
        reset_token = generate_password_reset_token(password_reset.email)
        
        # In production, send email with OTP
        # For now, return the token (for testing)
        return {
            "message": "Password reset OTP sent to your email",
            "reset_token": reset_token  # Remove this in production
        }
    
    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a password reset OTP has been sent"}


@router.post("/reset-password")
async def reset_password(password_reset: PasswordResetConfirm) -> Dict[str, str]:
    """
    Reset password endpoint.
    
    Requirements:
    - Verify OTP
    - Update password
    - Validate new password strength
    """
    email = verify_password_reset_token(password_reset.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    user = await supabase.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate new password strength
    if len(password_reset.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Update password
    await supabase.update_user(user["id"], {
        "hashed_password": get_password_hash(password_reset.new_password)
    })
    
    return {"message": "Password updated successfully"}


@router.post("/logout")
async def logout(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, str]:
    """
    Logout endpoint.
    
    Requirements:
    - Confirm logout
    - Invalidate token (in production, add to blacklist)
    """
    # In production, add token to blacklist
    return {"message": "Successfully logged out"}


@router.delete("/delete-account")
async def delete_account(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Delete account endpoint.
    
    Requirements:
    - Confirmation modal (handled by frontend)
    - Delete user data from database
    - Remove all associated data
    """
    try:
        # Delete user from Supabase
        # Note: This would require admin privileges in production
        # For now, we'll mark the account as deleted
        await supabase.update_user(current_user["id"], {
            "is_active": False,
            "deleted_at": "now()"
        })
        
        return {"message": "Account deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account. Please try again."
        )


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current user information."""
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "full_name": current_user.get("full_name"),
        "address": current_user.get("address"),
        "is_active": current_user.get("is_active", True),
        "email_verified": current_user.get("email_verified", False),
        "created_at": current_user.get("created_at"),
    } 