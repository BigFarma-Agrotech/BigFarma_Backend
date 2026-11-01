"""
API routes for wallet functionality
"""
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse, Response
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
    BankAccountVerificationError, DuplicateBankAccountError, BankAccountNotFoundError,
    PaymentGatewayError
)
from .models import WithdrawalRequest
from .config import wallet_config

logger = logging.getLogger(__name__)

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


def _error(status_code: int, code: str, message: str, **extra) -> JSONResponse:
    """Error body with both `detail` (what the frontend shows) and a machine-readable `error` code."""
    return JSONResponse(
        status_code=status_code,
        content={"error": code, "message": message, "detail": message, **extra},
    )


@router.get("/withdrawal-settings")
async def get_withdrawal_settings(current_user: User = Depends(get_current_farmer_user)):
    """Minimum amount and fee rules, so the app can show the fee before the farmer confirms."""
    return {
        "minimum_amount": wallet_config.MINIMUM_WITHDRAWAL_AMOUNT,
        "fee_percentage": wallet_config.WITHDRAWAL_FEE_PERCENTAGE,
        "maximum_fee": wallet_config.MAXIMUM_WITHDRAWAL_FEE,
        "currency": "NGN",
    }


@router.post("/withdraw", response_model=WithdrawalRequestResponse)
async def initiate_withdrawal(
    withdrawal_request: WithdrawalRequestCreate,
    current_user: User = Depends(get_current_farmer_user),
    withdrawal_service: WithdrawalService = Depends(get_withdrawal_service),
    _: None = Depends(ensure_wallet_exists)
):
    """
    Withdraw from the wallet to one of the farmer's linked bank accounts.

    The amount leaves the wallet at once and is sent by Paystack transfer, less the
    withdrawal fee. If the transfer fails the amount is credited back.
    """
    try:
        withdrawal = await withdrawal_service.create_withdrawal_request(current_user.id, withdrawal_request)
        return WithdrawalRequestResponse.model_validate(withdrawal)
    except InsufficientFundsException as e:
        return _error(400, "insufficient_funds", e.message,
                      available_balance=e.available, requested_amount=e.requested)
    except WithdrawalLimitException as e:
        return _error(400, "withdrawal_limit_error", e.message,
                      minimum_amount=wallet_config.MINIMUM_WITHDRAWAL_AMOUNT)
    except PendingWithdrawalError as e:
        return _error(409, "pending_withdrawal_exists", e.message)
    except (BankAccountNotFoundError, BankAccountVerificationError) as e:
        return _error(400, e.code, e.message)
    except PaymentGatewayError as e:
        return _error(502, e.code, e.message)
    except Exception:
        logger.exception("Withdrawal failed for farmer %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process withdrawal request"
        )


@router.get("/withdrawals", response_model=List[WithdrawalRequestResponse])
async def list_withdrawals(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_farmer_user),
    wallet_service: WalletService = Depends(get_wallet_service),
    _: None = Depends(ensure_wallet_exists)
):
    """The farmer's most recent withdrawals, newest first."""
    wallet = wallet_service.get_wallet_by_farmer_id(current_user.id)
    withdrawals = (
        wallet_service.db.query(WithdrawalRequest)
        .filter(WithdrawalRequest.wallet_id == wallet.id)
        .order_by(WithdrawalRequest.created_at.desc())
        .limit(limit)
        .all()
    )
    return [WithdrawalRequestResponse.model_validate(w) for w in withdrawals]


@router.get("/withdrawal/{withdrawal_id}", response_model=WithdrawalRequestResponse)
async def get_withdrawal_status(
    withdrawal_id: UUID,
    current_user: User = Depends(get_current_farmer_user),
    withdrawal_service: WithdrawalService = Depends(get_withdrawal_service),
    _: None = Depends(ensure_wallet_exists)
):
    """Status of one of the farmer's withdrawals."""
    try:
        withdrawal = withdrawal_service.get_withdrawal_status(withdrawal_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    wallet = withdrawal_service.wallet_service.get_wallet_by_farmer_id(current_user.id)
    if withdrawal.wallet_id != wallet.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Withdrawal not found")
    return WithdrawalRequestResponse.model_validate(withdrawal)


@router.post("/withdrawal/{withdrawal_id}/cancel", response_model=WithdrawalRequestResponse)
async def cancel_withdrawal(
    withdrawal_id: UUID,
    current_user: User = Depends(get_current_farmer_user),
    withdrawal_service: WithdrawalService = Depends(get_withdrawal_service),
    _: None = Depends(ensure_wallet_exists)
):
    """Cancel a withdrawal that hasn't been sent to the bank yet."""
    try:
        withdrawal = withdrawal_service.cancel_withdrawal(withdrawal_id, current_user.id)
        return WithdrawalRequestResponse.model_validate(withdrawal)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/banks")
async def list_banks(
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service)
):
    """Banks a farmer can withdraw to: [{name, code}]."""
    try:
        return {"banks": await bank_service.list_banks()}
    except PaymentGatewayError as e:
        return _error(502, e.code, e.message)


@router.post("/bank-accounts/verify", response_model=dict)
async def verify_bank_account(
    account_data: BankAccountCreateRequest,
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service)
):
    """Look up the name on an account, so the farmer can confirm it before adding it."""
    try:
        verification = await bank_service.verify_bank_account(account_data.account_number, account_data.bank_code)
    except BankAccountVerificationError as e:
        return _error(400, e.code, e.message)
    except PaymentGatewayError as e:
        return _error(502, e.code, e.message)
    return {
        "account_number": verification.account_number,
        "account_name": verification.account_name,
        "bank_name": verification.bank_name,
        "bank_code": verification.bank_code,
        "is_valid": verification.is_valid,
    }


@router.post("/bank-accounts", response_model=BankAccountResponse)
async def add_bank_account(
    account_data: BankAccountCreateRequest,
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service),
    _: None = Depends(ensure_wallet_exists)
):
    """Verify an account with Paystack, register it for transfers, and link it to the wallet."""
    try:
        verification = await bank_service.verify_bank_account(account_data.account_number, account_data.bank_code)
        verification = await bank_service.register_recipient(verification)
        bank_account = bank_service.add_bank_account(current_user.id, account_data, verification)
        return BankAccountResponse.model_validate(bank_account)
    except DuplicateBankAccountError as e:
        return _error(409, e.code, e.message)
    except BankAccountVerificationError as e:
        return _error(400, e.code, e.message)
    except PaymentGatewayError as e:
        return _error(502, e.code, e.message)


@router.get("/bank-accounts", response_model=List[BankAccountResponse])
async def get_bank_accounts(
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service),
    _: None = Depends(ensure_wallet_exists)
):
    """The farmer's linked bank accounts, primary first."""
    accounts = bank_service.get_bank_accounts(current_user.id)
    return [BankAccountResponse.model_validate(acc) for acc in accounts]


@router.put("/bank-accounts/{account_id}/primary", response_model=BankAccountResponse)
async def set_primary_bank_account(
    account_id: UUID,
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service),
    _: None = Depends(ensure_wallet_exists)
):
    """Make an account the default for withdrawals."""
    try:
        account = bank_service.set_primary_bank_account(current_user.id, account_id)
        return BankAccountResponse.model_validate(account)
    except BankAccountNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete("/bank-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bank_account(
    account_id: UUID,
    current_user: User = Depends(get_current_farmer_user),
    bank_service: BankVerificationService = Depends(get_bank_verification_service),
    _: None = Depends(ensure_wallet_exists)
):
    """Unlink a bank account."""
    try:
        bank_service.remove_bank_account(current_user.id, account_id)
    except BankAccountNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except BankAccountVerificationError as e:
        return _error(409, e.code, e.message)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Paystack transfer results (transfer.success / failed / reversed) arrive at the
# shared Paystack webhook in features/payments/routes.py.


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
