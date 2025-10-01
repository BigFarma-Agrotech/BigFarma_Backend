from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid
import enum


class TransactionType(str, enum.Enum):
    """Types of transactions"""
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionCategory(str, enum.Enum):
    """Categories of transactions"""
    PRODUCT_SALE = "product_sale"
    INVESTMENT_PAYOUT = "investment_payout"
    WITHDRAWAL = "withdrawal"
    DEPOSIT = "deposit"
    REFUND = "refund"
    BONUS = "bonus"


class WithdrawalStatus(str, enum.Enum):
    """Status of withdrawal requests"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BankAccountStatus(str, enum.Enum):
    """Status of bank account verification"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class Wallet(Base):
    """Wallet model for farmers"""
    __tablename__ = "wallets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farmer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    ledger_balance = Column(Float, default=0.0, nullable=False)  # Available for withdrawal
    currency = Column(String(3), default="NGN", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_transaction_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    farmer = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet", order_by="Transaction.created_at.desc()")
    withdrawal_requests = relationship("WithdrawalRequest", back_populates="wallet")
    bank_accounts = relationship("BankAccount", back_populates="wallet")
    
    def __repr__(self):
        return f"<Wallet(id={self.id}, farmer_id={self.farmer_id}, balance={self.balance})>"


class Transaction(Base):
    """Transaction records for wallet activities"""
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    reference = Column(String(100), unique=True, nullable=False)  # Unique transaction reference
    type = Column(Enum(TransactionType), nullable=False)
    category = Column(Enum(TransactionCategory), nullable=False)
    amount = Column(Float, nullable=False)
    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    description = Column(String(255), nullable=False)
    metadata = Column(Text, nullable=True)  # JSON field for additional data
    status = Column(String(50), default="completed", nullable=False)
    
    # Related entity references
    product_order_id = Column(UUID(as_uuid=True), nullable=True)  # Link to product sale
    investment_id = Column(UUID(as_uuid=True), nullable=True)  # Link to investment
    withdrawal_request_id = Column(UUID(as_uuid=True), ForeignKey("withdrawal_requests.id"), nullable=True)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")
    withdrawal_request = relationship("WithdrawalRequest", back_populates="transaction", uselist=False)
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, type={self.type}, amount={self.amount})>"


class WithdrawalRequest(BaseModel):
    """Withdrawal requests from wallet to bank account"""
    __tablename__ = "withdrawal_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.0, nullable=False)
    final_amount = Column(Float, nullable=False)  # Amount after fees
    reference = Column(String(100), unique=True, nullable=False)
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False)
    
    # Payment gateway references
    gateway_reference = Column(String(255), nullable=True)
    gateway_response = Column(Text, nullable=True)  # JSON response from payment gateway
    
    # Processing timestamps
    initiated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    # Idempotency
    idempotency_key = Column(String(255), unique=True, nullable=True)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="withdrawal_requests")
    bank_account = relationship("BankAccount")
    transaction = relationship("Transaction", back_populates="withdrawal_request", uselist=False)
    
    def __repr__(self):
        return f"<WithdrawalRequest(id={self.id}, amount={self.amount}, status={self.status})>"


class BankAccount(BaseModel):
    """Bank accounts linked to farmer wallets"""
    __tablename__ = "bank_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    account_number = Column(String(20), nullable=False)
    account_name = Column(String(255), nullable=False)
    bank_code = Column(String(10), nullable=False)
    bank_name = Column(String(255), nullable=False)
    status = Column(Enum(BankAccountStatus), default=BankAccountStatus.PENDING, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Verification details
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_reference = Column(String(255), nullable=True)
    recipient_code = Column(String(255), nullable=True)  # Payment gateway recipient code
    
    # Metadata
    metadata = Column(Text, nullable=True)  # Additional bank-specific data
    
    # Relationships
    wallet = relationship("Wallet", back_populates="bank_accounts")
    
    # Unique constraint for wallet + account number + bank code
    __table_args__ = (
        UniqueConstraint('wallet_id', 'account_number', 'bank_code', name='_wallet_account_bank_uc'),
    )
    
    def __repr__(self):
        return f"<BankAccount(id={self.id}, account_name={self.account_name}, bank={self.bank_name})>"


# Import after model definitions to avoid circular imports
from sqlalchemy import UniqueConstraint