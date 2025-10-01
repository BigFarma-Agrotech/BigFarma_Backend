"""
Dependency injection for wallet services
"""
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from database import get_db
from features.auth.models import User
from core.dependencies import get_current_user
from .services import WalletService, WithdrawalService, BankVerificationService


def get_wallet_service(db: Session = Depends(get_db)) -> WalletService:
    """
    Get wallet service instance
    
    Args:
        db: Database session
    
    Returns:
        WalletService instance
    """
    return WalletService(db)


def get_withdrawal_service(
    db: Session = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service)
) -> WithdrawalService:
    """
    Get withdrawal service instance
    
    Args:
        db: Database session
        wallet_service: Wallet service instance
    
    Returns:
        WithdrawalService instance
    """
    return WithdrawalService(db, wallet_service)


def get_bank_verification_service(db: Session = Depends(get_db)) -> BankVerificationService:
    """
    Get bank verification service instance
    
    Args:
        db: Database session
    
    Returns:
        BankVerificationService instance
    """
    return BankVerificationService(db)


def get_current_farmer_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify they are a farmer
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        User object if they are a farmer
    
    Raises:
        HTTPException: If user is not a farmer
    """
    from fastapi import HTTPException, status
    
    # Assuming there's a role or user_type field to check
    # Adjust based on your actual User model
    if hasattr(current_user, 'user_type') and current_user.user_type != 'farmer':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only farmers can access wallet features"
        )
    
    return current_user


def ensure_wallet_exists(
    current_user: User = Depends(get_current_farmer_user),
    wallet_service: WalletService = Depends(get_wallet_service)
) -> None:
    """
    Ensure that the current farmer has a wallet, create if not exists
    
    Args:
        current_user: Current farmer user
        wallet_service: Wallet service instance
    """
    try:
        wallet_service.get_wallet_by_farmer_id(current_user.id)
    except:
        # Create wallet if it doesn't exist
        wallet_service.create_wallet(current_user.id)
