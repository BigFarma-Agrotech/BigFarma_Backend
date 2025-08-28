from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db
from features.auth.schemas import UserCreate, UserLogin, Token, OTPRequest, OTPVerify, PasswordResetRequest, PasswordReset
from features.auth.service import AuthService
from features.auth.models import OTPMedium
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
        "refresh_token": refresh_token
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
    
    # Verify OTP
    if not auth_service.verify_otp(user.id, otp_verify.code, otp_verify.medium):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Mark user as verified for verification OTPs
    if otp_verify.otp_type == "verification" and not user.is_verified:
        success = auth_service.mark_user_verified(user.id)
        if not success:
            raise HTTPException(status_code=500, detail="Error updating verification status")
    
    return {"message": "OTP verified successfully"}

@router.post("/password-reset-request")
async def password_reset_request(reset_request: PasswordResetRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    user = auth_service.get_user_by_email_or_phone(
        email=reset_request.email,
        phone=reset_request.phone
    )
    
    if user:
        background_tasks.add_task(
            auth_service.request_otp,
            user.id, reset_request.medium, reset_request.email, reset_request.phone, "password_reset"
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
    
    if not auth_service.verify_otp(user.id, reset_data.code, reset_data.medium):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    from core.security import get_password_hash
    user_repo = UserRepository(db)
    user_repo.update(user.id, password=get_password_hash(reset_data.new_password))
    
    return {"message": "Password reset successfully"}