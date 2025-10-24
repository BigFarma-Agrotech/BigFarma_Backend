from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# Enums matching the models
class TransactionTypeSchema(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionCategorySchema(str, Enum):
    PRODUCT_SALE = "product_sale"
    INVESTMENT_PAYOUT = "investment_payout"
    WITHDRAWAL = "withdrawal"
    DEPOSIT = "deposit"
    REFUND = "refund"
    BONUS = "bonus"


class WithdrawalStatusSchema(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BankAccountStatusSchema(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


# Base schemas
class WalletBase(BaseModel):
    balance: float = Field(..., ge=0, description="Wallet balance")
    ledger_balance: float = Field(..., ge=0, description="Available balance for withdrawal")
    currency: str = Field(default="NGN", max_length=3)


class TransactionBase(BaseModel):
    type: TransactionTypeSchema
    category: TransactionCategorySchema
    amount: float = Field(..., gt=0)
    description: str = Field(..., max_length=255)


class WithdrawalBase(BaseModel):
    amount: float = Field(..., gt=0)
    bank_account_id: UUID


class BankAccountBase(BaseModel):
    account_number: str = Field(..., max_length=20, pattern="^[0-9]{10}$")
    bank_code: str = Field(..., max_length=10)
    
    @field_validator("account_number")
    def validate_account_number(cls, v):
        if not v.isdigit() or len(v) != 10:
            raise ValueError('Account number must be 10 digits')
        return v


# Request schemas
class BankAccountCreateRequest(BankAccountBase):
    """Request schema for adding a new bank account"""
    pass


class BankAccountVerifyResponse(BaseModel):
    """Response from bank verification service"""
    account_number: str
    account_name: str
    bank_code: str
    bank_name: str
    is_valid: bool
    recipient_code: Optional[str] = None


class WithdrawalRequestCreate(WithdrawalBase):
    """Request schema for initiating withdrawal"""
    idempotency_key: Optional[str] = Field(None, max_length=255)
    
    @field_validator("amount")
    def validate_minimum_amount(cls, v):
        if v < 500:
            raise ValueError('Minimum withdrawal amount is ₦500')
        return v


class TransactionFilter(BaseModel):
    """Filter schema for transaction history"""
    type: Optional[TransactionTypeSchema] = None
    category: Optional[TransactionCategorySchema] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


# Response schemas
class WalletResponse(BaseModel):
    """Response schema for wallet details"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    balance: float
    ledger_balance: float
    currency: str
    is_active: bool
    last_transaction_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class TransactionResponse(BaseModel):
    """Response schema for transaction details"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    reference: str
    type: TransactionTypeSchema
    category: TransactionCategorySchema
    amount: float
    balance_before: float
    balance_after: float
    description: str
    status: str
    created_at: datetime


class TransactionListResponse(BaseModel):
    """Response schema for paginated transaction list"""
    transactions: List[TransactionResponse]
    total: int
    page: int
    limit: int
    has_next: bool


class BankAccountResponse(BaseModel):
    """Response schema for bank account details"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    account_number: str
    account_name: str
    bank_code: str
    bank_name: str
    status: BankAccountStatusSchema
    is_primary: bool
    is_active: bool
    verified_at: Optional[datetime]
    created_at: datetime


class WithdrawalRequestResponse(BaseModel):
    """Response schema for withdrawal request"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    amount: float
    fee: float
    final_amount: float
    reference: str
    status: WithdrawalStatusSchema
    bank_account: BankAccountResponse
    initiated_at: datetime
    processed_at: Optional[datetime]
    completed_at: Optional[datetime]
    failure_reason: Optional[str]


class WalletDashboardResponse(BaseModel):
    """Response schema for wallet dashboard data"""
    wallet: WalletResponse
    recent_transactions: List[TransactionResponse]
    pending_withdrawals: List[WithdrawalRequestResponse]
    total_earnings: float
    total_withdrawals: float


# Error response schemas
class WalletErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class InsufficientFundsError(WalletErrorResponse):
    """Error response for insufficient funds"""
    error: str = "insufficient_funds"
    available_balance: float
    requested_amount: float


class WithdrawalLimitError(WalletErrorResponse):
    """Error response for withdrawal limit violations"""
    error: str = "withdrawal_limit_error"
    minimum_amount: float = 500
    maximum_amount: Optional[float] = None
