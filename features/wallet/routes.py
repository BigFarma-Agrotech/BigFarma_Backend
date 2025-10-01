"""
API routes for wallet functionality
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from features.auth.models import User
from database import get_db
from .schemas import (
    WalletResponse, WalletDashboardResponse, TransactionResponse,
    TransactionListResponse, TransactionFilter, WithdrawalRequestCreate,
    WithdrawalRequestResponse, BankAccountCreateRequest, BankAccountResponse,
    InsufficientFundsError, WithdrawalLimitError, WalletErrorResponse
)
from .dependencies import (
    get_wallet_service, get_withdrawal_service, get_bank_verification_service,
    get_current_farmer_user, ensure_wallet_exists
)
from .services import WalletService, WithdrawalService, BankVerificationService
from .exceptions import (
    WalletException, InsufficientFundsError as InsufficientFundsException,
    WithdrawalLimitError as WithdrawalLimitException, PendingWithdrawalError,
    BankAccountVerificationError, DuplicateBankAccountError
)

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("/balance", response_model=dict)
async def get_wallet_balance(
    current_user: User = Depends(get_current_farmer_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    _: None = Depends(ensure_wallet_exists)
):
    """
    Get current wallet balance
    
    Returns wallet balance, ledger balance, and last transaction time
    """
    try:
        balance_info = wallet_service.get_wallet_balance(current_user.id)
        return balance_info
    except WalletException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


@router.get("/dashboard", response_model=WalletDashboardResponse)
async def get_wallet_dashboard(
    current_user: User = Depends(get_current_farmer_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    _: None = Depends(ensure_wallet_exists)
):
    """
    Get comprehensive wallet dashboard data
    
    Returns wallet info, recent transactions, pending withdrawals, and statistics
    """
    try:
        dashboard_data = wallet_service.get_wallet_dashboard(current_user.id)
        return WalletDashboardResponse(**dashboard_data)
    except WalletException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


@router.get("/transactions", response_model=TransactionListResponse)
async def get_transaction_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    type: Optional[str] = Query(None, description="Transaction type (credit/debit)"),
    category: Optional[str] = Query(None, description="Transaction category"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    current_user: User = Depends(get_current_farmer_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    _: None = Depends(ensure_wallet_exists)
):
    """
    Get paginated transaction history with optional filters
    """
    try:
        filter_params = TransactionFilter(
            page=page,
            limit=limit,
            type=type,
            category=category,
            start_date=start_date,
            end_date=end_date
        )
        
        result = wallet_service.get_transaction_history(current_user.id, filter_params)
        
        return TransactionListResponse(
            transactions=[TransactionResponse.model_validate(t) for t in result["transactions"]],
            total=result["total"],
            page=result["page"],
            limit=result["limit"],
            has_next=result["has_next"]
        )
    except WalletException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


@router.post("/withdraw", response_model=WithdrawalRequestResponse)
async def initiate_withdrawal(
    withdrawal_request: WithdrawalRequestCreate,
    current_user: User = Depends(get_current_farmer_user),
    withdrawal_service: WithdrawalService = Depends(get_withdrawal_service),
    _: None = Depends(ensure_wallet_exists)
):
    """
    Initiate a withdrawal request
    
    Minimum withdrawal amount is ₦500
    """
    try:
        withdrawal = withdrawal_service.create_withdrawal_request(
            current_user.id,
            withdrawal_request
        )
        return WithdrawalRequestResponse.model_validate(withdrawal)
    
    except InsufficientFundsException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=InsufficientFundsError(
                message=e.message,
                available_balance=e.available,
                requested_amount=e.requested
            ).model_dump()
        )
    
    except WithdrawalLimitException as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=WithdrawalLimitError(
                message=e.message
            ).model_dump()
        )
    
    except PendingWithdrawalError as e:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=WalletErrorResponse(
                error="pending_withdrawal_exists",
                message=e.message
            ).model_dump()
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process withdrawal request"
        )


@router.get("/withdrawal/{withdrawal_id}", response_model=WithdrawalRequestResponse)
async def get_withdrawal_status(
    withdrawal_id: UUID,
    current_user: User = Depends(get_current_farmer_user),
    withdrawal_service: WithdrawalService = Depends(get_withdrawal_service)
):
    """
    Get status of a specific withdrawal request
    """
    try:
        withdrawal = withdrawal_service.get_withdrawal_status(withdrawal_id)
        
        # Verify ownership
        wallet_service = WalletService(withdrawal_service.db)
        wallet = wallet_service.get_wallet_by_farmer_id(current_user.id)
        
        if withdrawal.wallet_id != wallet.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this withdrawal request"
            )
        
        return WithdrawalRequestResponse.model_validate(withdrawal)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/withdrawal/{withdrawal_id}/cancel", response_model=WithdrawalRequestResponse)
async def cancel_withdrawal(
    withdrawal_id: UUID,
    current_user: User = Depends(get_current_farmer_user),
    withdrawal_service: WithdrawalService = Depends(get_withdrawal_service)
):
    """
    Cancel a pending withdrawal request
    """
    try:
        withdrawal = withdrawal_service.cancel_withdrawal(withdrawal_id, current_user.id)
        return WithdrawalRequestResponse.model_validate(withdrawal)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/bank-accounts/verify", response_model=dict)
async def verify_bank_account(
    account_data: BankAccountCreateRequest,
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service)
):
    """
    Verify bank account details before adding
    """
    try:
        verification = await bank_service.verify_bank_account(
            account_data.account_number,
            account_data.bank_code
        )
        
        if not verification.is_valid:
            raise BankAccountVerificationError()
        
        return {
            "account_number": verification.account_number,
            "account_name": verification.account_name,
            "bank_name": verification.bank_name,
            "bank_code": verification.bank_code,
            "is_valid": verification.is_valid
        }
    
    except BankAccountVerificationError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=WalletErrorResponse(
                error=e.code,
                message=e.message
            ).model_dump()
        )


@router.post("/bank-accounts", response_model=BankAccountResponse)
async def add_bank_account(
    account_data: BankAccountCreateRequest,
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service),
    _: None = Depends(ensure_wallet_exists)
):
    """
    Add a new bank account after verification
    """
    try:
        # First verify the account
        verification = await bank_service.verify_bank_account(
            account_data.account_number,
            account_data.bank_code
        )
        
        if not verification.is_valid:
            raise BankAccountVerificationError()
        
        # Add the verified account
        bank_account = bank_service.add_bank_account(
            current_user.id,
            account_data,
            verification
        )
        
        return BankAccountResponse.model_validate(bank_account)
    
    except DuplicateBankAccountError as e:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=WalletErrorResponse(
                error=e.code,
                message=e.message
            ).model_dump()
        )
    
    except BankAccountVerificationError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=WalletErrorResponse(
                error=e.code,
                message=e.message
            ).model_dump()
        )


@router.get("/bank-accounts", response_model=List[BankAccountResponse])
async def get_bank_accounts(
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service),
    _: None = Depends(ensure_wallet_exists)
):
    """
    Get all bank accounts for the current farmer
    """
    try:
        accounts = bank_service.get_bank_accounts(current_user.id)
        return [BankAccountResponse.model_validate(acc) for acc in accounts]
    
    except WalletException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


@router.put("/bank-accounts/{account_id}/primary", response_model=BankAccountResponse)
async def set_primary_bank_account(
    account_id: UUID,
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service)
):
    """
    Set a bank account as primary
    """
    try:
        account = bank_service.set_primary_bank_account(current_user.id, account_id)
        return BankAccountResponse.model_validate(account)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# Webhook endpoints for payment gateway callbacks (internal use)
@router.post("/webhooks/withdrawal-status", include_in_schema=False)
async def handle_withdrawal_webhook(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Handle withdrawal status updates from payment gateway
    
    This endpoint would be called by the payment gateway to update withdrawal status
    """
    # Implementation would depend on your payment gateway
    # This is a placeholder for the webhook handler
    return {"status": "ok"}


# Admin endpoints (if needed)
@router.get("/admin/stats", include_in_schema=False)
async def get_wallet_statistics(
    db: Session = Depends(get_db)
    # Add admin authentication dependency
):
    """
    Get overall wallet statistics for admin dashboard
    """
    # Implementation for admin statistics
    return {"status": "not_implemented"}
