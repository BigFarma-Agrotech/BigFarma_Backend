from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db
from features.auth.schemas import UserCreate, UserLogin, Token, OTPRequest, OTPVerify, PasswordReset
from features.auth.service import AuthService
from features.auth.models import OTPMedium, OTPType
from core.security import create_access_token, create_refresh_token
from repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        db_user = auth_service.create_user(user)
        return {"message": "User registered successfully", "user_id": db_user.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=Token)
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(user_login.login, user_login.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Account not verified")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "user_category": user.category.value,
        "profile_setup": user.profile_setup
    }

@router.post("/request-otp")
async def request_otp(otp_request: OTPRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    
    user = auth_service.get_user_by_email_or_phone(
        email=otp_request.email,
        phone=otp_request.phone
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify medium matches user record
    if (otp_request.medium == OTPMedium.EMAIL and user.email != otp_request.email) or \
       (otp_request.medium == OTPMedium.PHONE and user.phone_number != otp_request.phone):
        raise HTTPException(status_code=400, detail="Contact method doesn't match user record")
    
    background_tasks.add_task(
        auth_service.request_otp,
        user.id, otp_request.medium, otp_request.email, otp_request.phone, otp_request.otp_type
    )
    
    return {"message": "OTP sent successfully"}

@router.post("/verify-otp")
async def verify_otp(otp_verify: OTPVerify, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    
    user = auth_service.get_user_by_email_or_phone(
        email=otp_verify.email,
        phone=otp_verify.phone
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify medium matches user record
    if (otp_verify.medium == OTPMedium.EMAIL and user.email != otp_verify.email) or \
       (otp_verify.medium == OTPMedium.PHONE and user.phone_number != otp_verify.phone):
        raise HTTPException(status_code=400, detail="Contact method doesn't match user record")
    
    # Verify OTP based on type
    if not auth_service.verify_otp(user.id, otp_verify.code, otp_verify.medium, otp_verify.otp_type):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Handle different OTP types
    if otp_verify.otp_type == OTPType.VERIFICATION:
        # Mark user as verified for account verification
        if not user.is_verified:
            success = auth_service.mark_user_verified(user.id)
            if not success:
                raise HTTPException(status_code=500, detail="Error updating verification status")
            # Delete the verified OTP
            auth_service.delete_verified_otp(user.id, otp_verify.medium, otp_verify.otp_type)
        return {"message": "Account verified successfully"}
    
    elif otp_verify.otp_type == OTPType.PASSWORD_RESET:
        # For password reset, just mark OTP as verified (password reset happens in separate endpoint)
        return {"message": "OTP verified for password reset. You can now reset your password."}
    
    raise HTTPException(status_code=400, detail="Invalid OTP type")

@router.post("/password-reset")
async def password_reset(reset_data: PasswordReset, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    user = auth_service.get_user_by_email_or_phone(
        email=reset_data.email,
        phone=reset_data.phone
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if password reset OTP has been verified
    if not auth_service.is_otp_verified(user.id, reset_data.medium, OTPType.PASSWORD_RESET):
        raise HTTPException(status_code=400, detail="Password reset OTP not verified. Please verify OTP first.")
    
    # Reset password
    success = auth_service.reset_password(user.id, reset_data.new_password)
    if not success:
        raise HTTPException(status_code=500, detail="Error resetting password")
    
    # Delete the verified OTP after successful password reset
    auth_service.delete_verified_otp(user.id, reset_data.medium, OTPType.PASSWORD_RESET)
    
    return {"message": "Password reset successfully"}
