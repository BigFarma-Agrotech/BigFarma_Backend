from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db
from features.auth.schemas import (
    UserCreate, UserLogin, Token, OTPRequest, 
    OTPVerify, PasswordResetRequest, PasswordReset
)
from features.auth.service import AuthService
from core.security import create_access_token, create_refresh_token

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
    user = auth_service.get_user_by_identifier(otp_request.destination)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify the medium matches the user's registered contact method
    from features.auth.models import OTPMedium
    if otp_request.medium == OTPMedium.EMAIL and user.email != otp_request.destination:
        raise HTTPException(status_code=400, detail="Email does not match user record")
    
    if otp_request.medium == OTPMedium.PHONE and user.phone_number != otp_request.destination:
        raise HTTPException(status_code=400, detail="Phone number does not match user record")
    
    # Send OTP in background
    background_tasks.add_task(
        auth_service.request_otp,
        user.id, otp_request.medium, otp_request.destination, otp_request.otp_type
    )
    
    return {"message": "OTP sent successfully"}

@router.post("/verify-otp")
async def verify_otp(otp_verify: OTPVerify, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    
    # Find user by email or phone number
    user = auth_service.get_user_by_identifier(otp_verify.destination)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify OTP
    is_valid = auth_service.verify_otp(user.id, otp_verify.code, otp_verify.medium)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Mark user as verified if this is a verification OTP
    if otp_verify.otp_type == "verification" and not user.is_verified:
        from repositories import UserRepository
        user_repo = UserRepository(db)
        user_repo.update(user.id, is_verified=True)
    
    return {"message": "OTP verified successfully"}

@router.post("/password-reset-request")
async def password_reset_request(
    reset_request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    
    user = auth_service.get_user_by_identifier(reset_request.destination)
    if not user:
        # Don't reveal whether user exists for security
        return {"message": "If the account exists, a password reset code has been sent"}
    
    # Verify the medium matches the user's registered contact method
    from features.auth.models import OTPMedium
    if reset_request.medium == OTPMedium.EMAIL and user.email != reset_request.destination:
        raise HTTPException(status_code=400, detail="Email does not match user record")
    
    if reset_request.medium == OTPMedium.PHONE and user.phone_number != reset_request.destination:
        raise HTTPException(status_code=400, detail="Phone number does not match user record")
    
    # Send OTP in background
    background_tasks.add_task(
        auth_service.request_otp,
        user.id, reset_request.medium, reset_request.destination, "password_reset"
    )
    
    return {"message": "Password reset code has been sent"}

@router.post("/password-reset")
async def password_reset(reset_data: PasswordReset, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    
    user = auth_service.get_user_by_identifier(reset_data.destination)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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