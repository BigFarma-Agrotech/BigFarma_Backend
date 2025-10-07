import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import CHAR, TypeDecorator

from database import Base
from features.auth.models import User  # noqa: F401


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type."""

    impl = PGUUID
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


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

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    farmer_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    ledger_balance = Column(Float, default=0.0, nullable=False)
    currency = Column(String(3), default="NGN", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_transaction_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    farmer = relationship("User", back_populates="wallet")
    transactions = relationship(
        "Transaction",
        back_populates="wallet",
        order_by="Transaction.created_at.desc()",
    )
    withdrawal_requests = relationship("WithdrawalRequest", back_populates="wallet")
    bank_accounts = relationship("BankAccount", back_populates="wallet")

    def __repr__(self):
        return f"<Wallet(id={self.id}, farmer_id={self.farmer_id}, balance={self.balance})>"


class Transaction(Base):
    """Transaction records for wallet activities"""

    __tablename__ = "transactions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(GUID(), ForeignKey("wallets.id"), nullable=False)
    reference = Column(String(100), unique=True, nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    category = Column(Enum(TransactionCategory), nullable=False)
    amount = Column(Float, nullable=False)
    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    description = Column(String(255), nullable=False)
    metadata_json = Column("metadata", Text, nullable=True)
    status = Column(String(50), default="completed", nullable=False)
    product_order_id = Column(GUID(), nullable=True)
    investment_id = Column(GUID(), nullable=True)
    withdrawal_request_id = Column(GUID(), ForeignKey("withdrawal_requests.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet = relationship("Wallet", back_populates="transactions")
    withdrawal_request = relationship("WithdrawalRequest", back_populates="transaction", uselist=False)

    def __repr__(self):
        return f"<Transaction(id={self.id}, type={self.type}, amount={self.amount})>"


class WithdrawalRequest(Base):
    """Withdrawal requests from wallet to bank account"""

    __tablename__ = "withdrawal_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(GUID(), ForeignKey("wallets.id"), nullable=False)
    bank_account_id = Column(GUID(), ForeignKey("bank_accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.0, nullable=False)
    final_amount = Column(Float, nullable=False)
    reference = Column(String(100), unique=True, nullable=False)
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False)
    gateway_reference = Column(String(255), nullable=True)
    gateway_response = Column(Text, nullable=True)
    initiated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    idempotency_key = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet = relationship("Wallet", back_populates="withdrawal_requests")
    bank_account = relationship("BankAccount")
    transaction = relationship("Transaction", back_populates="withdrawal_request", uselist=False)

    def __repr__(self):
        return f"<WithdrawalRequest(id={self.id}, amount={self.amount}, status={self.status})>"


class BankAccount(Base):
    """Bank accounts linked to farmer wallets"""

    __tablename__ = "bank_accounts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(GUID(), ForeignKey("wallets.id"), nullable=False)
    account_number = Column(String(20), nullable=False)
    account_name = Column(String(255), nullable=False)
    bank_code = Column(String(10), nullable=False)
    bank_name = Column(String(255), nullable=False)
    status = Column(Enum(BankAccountStatus), default=BankAccountStatus.PENDING, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_reference = Column(String(255), nullable=True)
    recipient_code = Column(String(255), nullable=True)
    metadata_json = Column("metadata", Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet = relationship("Wallet", back_populates="bank_accounts")

    __table_args__ = (
        UniqueConstraint("wallet_id", "account_number", "bank_code", name="_wallet_account_bank_uc"),
    )

    def __repr__(self):
        return f"<BankAccount(id={self.id}, account_name={self.account_name}, bank={self.bank_name})>"
