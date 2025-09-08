from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import logging
import traceback

from database import get_db
from features.auth.schemas import (
    UserCreate, UserLogin, Token, OTPRequest, 
    OTPVerify, PasswordResetRequest, PasswordReset
)
from features.auth.service import AuthService
from features.auth.models import OTPMedium
from core.security import create_access_token, create_refresh_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    
    try:
        db_user = auth_service.create_user(user)
        return {
            "message": "User registered successfully.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=Token)
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    
    user = auth_service.authenticate_user(user_login.login, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified. Please verify your account.",
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {
        "user_category": user.category,
        "access_token": access_token, 
        "token_type": "bearer",
        "refresh_token": refresh_token
    }

@router.post("/request-otp")
async def request_otp(
    otp_request: OTPRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    
    # Find user by email or phone number
    user = auth_service.get_user_by_email_or_phone(
        email=otp_request.email,
        phone=otp_request.phone
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify the medium matches the provided contact method
    if otp_request.medium == OTPMedium.EMAIL and not otp_request.email:
        raise HTTPException(status_code=400, detail="Email is required for email OTP")
    
    if otp_request.medium == OTPMedium.PHONE and not otp_request.phone:
        raise HTTPException(status_code=400, detail="Phone is required for phone OTP")
    
    # Verify the medium matches the user's registered contact method
    if (otp_request.medium == OTPMedium.EMAIL and 
        otp_request.email and user.email != otp_request.email):
        raise HTTPException(status_code=400, detail="Email does not match user record")
    
    if (otp_request.medium == OTPMedium.PHONE and 
        otp_request.phone and user.phone_number != otp_request.phone):
        raise HTTPException(status_code=400, detail="Phone number does not match user record")
    
    # Send OTP in background
    background_tasks.add_task(
        auth_service.request_otp,
        user.id, 
        otp_request.medium, 
        otp_request.email,
        otp_request.phone,
        otp_request.otp_type
    )
    
    return {"message": "OTP sent successfully"}


@router.post("/verify-otp")
async def verify_otp(otp_verify: OTPVerify, db: Session = Depends(get_db)):
    try:
        auth_service = AuthService(db)
        
        # Find user by email or phone number
        user = auth_service.get_user_by_email_or_phone(
            email=otp_verify.email,
            phone=otp_verify.phone
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify the medium matches the provided contact method
        if otp_verify.medium == OTPMedium.EMAIL and not otp_verify.email:
            raise HTTPException(status_code=400, detail="Email is required for email OTP verification")
        
        if otp_verify.medium == OTPMedium.PHONE and not otp_verify.phone:
            raise HTTPException(status_code=400, detail="Phone is required for phone OTP verification")
        
        # Verify the medium matches the user's registered contact method
        if (otp_verify.medium == OTPMedium.EMAIL and 
            otp_verify.email and user.email != otp_verify.email):
            raise HTTPException(status_code=400, detail="Email does not match user record")
        
        if (otp_verify.medium == OTPMedium.PHONE and 
            otp_verify.phone and user.phone_number != otp_verify.phone):
            raise HTTPException(status_code=400, detail="Phone number does not match user record")
        
        # Verify OTP
        is_valid = auth_service.verify_otp(user.id, otp_verify.code, otp_verify.medium)
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        
        # Mark user as verified if this is a verification OTP
        if otp_verify.otp_type == "verification" and not user.is_verified:
            from repositories import UserRepository
            user_repo = UserRepository(db)
            user_repo.update(user.id, is_verified=True)
            db.refresh(user)
        
        return {"message": "OTP verified successfully"}
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        logger.error(f"OTP verification error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error during OTP verification")


@router.post("/password-reset-request")
async def password_reset_request(
    reset_request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    
    user = auth_service.get_user_by_email_or_phone(
        email=reset_request.email,
        phone=reset_request.phone
    )
    if not user:
        # Don't reveal whether user exists for security
        return {"message": "If the account exists, a password reset code has been sent"}
    
    # Verify the medium matches the provided contact method
    if reset_request.medium == OTPMedium.EMAIL and not reset_request.email:
        raise HTTPException(status_code=400, detail="Email is required for email password reset")
    
    if reset_request.medium == OTPMedium.PHONE and not reset_request.phone:
        raise HTTPException(status_code=400, detail="Phone is required for phone password reset")
    
    # Verify the medium matches the user's registered contact method
    if (reset_request.medium == OTPMedium.EMAIL and 
        reset_request.email and user.email != reset_request.email):
        raise HTTPException(status_code=400, detail="Email does not match user record")
    
    if (reset_request.medium == OTPMedium.PHONE and 
        reset_request.phone and user.phone_number != reset_request.phone):
        raise HTTPException(status_code=400, detail="Phone number does not match user record")
    
    # Send OTP in background
    background_tasks.add_task(
        auth_service.request_otp,
        user.id, 
        reset_request.medium, 
        reset_request.email,
        reset_request.phone,
        "password_reset"
    )
    
    return {"message": "If the account exists, a password reset code has been sent"}

@router.post("/password-reset")
async def password_reset(reset_data: PasswordReset, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    
    user = auth_service.get_user_by_email_or_phone(
        email=reset_data.email,
        phone=reset_data.phone
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify the medium matches the provided contact method
    if reset_data.medium == OTPMedium.EMAIL and not reset_data.email:
        raise HTTPException(status_code=400, detail="Email is required for email password reset")
    
    if reset_data.medium == OTPMedium.PHONE and not reset_data.phone:
        raise HTTPException(status_code=400, detail="Phone is required for phone password reset")
    
    # Verify OTP
    is_valid = auth_service.verify_otp(user.id, reset_data.code, reset_data.medium)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Update password
    from core.security import get_password_hash
    from repositories import UserRepository
    user_repo = UserRepository(db)
    user_repo.update(user.id, password=get_password_hash(reset_data.new_password))
    
    return {"message": "Password reset successfully"}