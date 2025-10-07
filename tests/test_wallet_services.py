import sys
from pathlib import Path
import os

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ["DEBUG"] = "false"
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")

import pytest
from sqlalchemy import create_engine
import features.users.models  # noqa: F401
from sqlalchemy.orm import sessionmaker
import features.marketplace.models  # noqa: F401
import features.orders.models  # noqa: F401
from sqlalchemy.pool import StaticPool

from database import Base
from features.auth.models import User, UserCategory
from features.wallet.models import WithdrawalStatus, TransactionCategory
from features.wallet.services import WalletService, WithdrawalService, BankVerificationService
from features.wallet.schemas import (
    BankAccountCreateRequest,
    BankAccountVerifyResponse,
    WithdrawalRequestCreate,
    TransactionFilter,
    TransactionTypeSchema,
)
from features.wallet.exceptions import InsufficientFundsError


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def create_farmer(session, email="farmer@example.com"):
    farmer = User(
        email=email,
        password="hashed-password",
        category=UserCategory.FARMER,
        profile_setup=True,
        is_verified=True,
        is_active=True,
    )
    session.add(farmer)
    session.commit()
    session.refresh(farmer)
    return farmer


def seed_wallet_with_balance(session, farmer_id, amount=2_000.0):
    wallet_service = WalletService(session)
    wallet = wallet_service.create_wallet(farmer_id)
    wallet_service.credit_wallet(
        wallet_id=wallet.id,
        amount=amount,
        category=TransactionCategory.PRODUCT_SALE,
        description="Initial funding",
    )
    session.refresh(wallet)
    return wallet, wallet_service


def test_wallet_credit_and_debit_flow(db_session):
    farmer = create_farmer(db_session)
    wallet, wallet_service = seed_wallet_with_balance(db_session, farmer.id, amount=1_000.0)

    assert wallet.balance == pytest.approx(1_000.0)
    assert wallet.ledger_balance == pytest.approx(1_000.0)

    txn = wallet_service.debit_wallet(
        wallet_id=wallet.id,
        amount=250.0,
        category=TransactionCategory.WITHDRAWAL,
        description="Payout to farmer",
    )
    db_session.refresh(wallet)

    assert txn.amount == 250.0
    assert wallet.balance == pytest.approx(750.0)
    assert wallet.ledger_balance == pytest.approx(750.0)

    with pytest.raises(InsufficientFundsError):
        wallet_service.debit_wallet(
            wallet_id=wallet.id,
            amount=2_000.0,
            category=TransactionCategory.WITHDRAWAL,
            description="Overdraft attempt",
        )


def test_transaction_history_and_dashboard(db_session):
    farmer = create_farmer(db_session, email="farmer2@example.com")
    wallet_service = WalletService(db_session)
    wallet = wallet_service.create_wallet(farmer.id)

    wallet_service.credit_wallet(
        wallet_id=wallet.id,
        amount=500.0,
        category=TransactionCategory.PRODUCT_SALE,
        description="Sale #1",
    )
    wallet_service.credit_wallet(
        wallet_id=wallet.id,
        amount=300.0,
        category=TransactionCategory.BONUS,
        description="Promo bonus",
    )
    wallet_service.debit_wallet(
        wallet_id=wallet.id,
        amount=150.0,
        category=TransactionCategory.WITHDRAWAL,
        description="Partial withdrawal",
    )

    credit_history = wallet_service.get_transaction_history(
        farmer.id,
        TransactionFilter(type=TransactionTypeSchema.CREDIT, page=1, limit=20),
    )
    assert credit_history["total"] == 2
    assert all(tx.type.value == "credit" for tx in credit_history["transactions"])

    dashboard = wallet_service.get_wallet_dashboard(farmer.id)
    assert dashboard["wallet"].balance == pytest.approx(650.0)
    assert dashboard["total_earnings"] == pytest.approx(500.0)
    assert dashboard["total_withdrawals"] == pytest.approx(150.0)
    assert len(dashboard["recent_transactions"]) == 3


def test_withdrawal_and_bank_account_workflow(db_session):
    farmer = create_farmer(db_session, email="farmer3@example.com")
    wallet, wallet_service = seed_wallet_with_balance(db_session, farmer.id, amount=1_500.0)
    bank_service = BankVerificationService(db_session)

    account_request = BankAccountCreateRequest(account_number="1234567890", bank_code="058")
    verification = BankAccountVerifyResponse(
        account_number="1234567890",
        account_name="JOHN DOE",
        bank_code="058",
        bank_name="Guaranty Trust Bank",
        is_valid=True,
        recipient_code="RCP_1234567890",
    )

    bank_account = bank_service.add_bank_account(farmer.id, account_request, verification)
    all_accounts = bank_service.get_bank_accounts(farmer.id)
    assert len(all_accounts) == 1
    assert all_accounts[0].is_primary is True

    second_request = BankAccountCreateRequest(account_number="0987654321", bank_code="057")
    second_verification = BankAccountVerifyResponse(
        account_number="0987654321",
        account_name="JANE DOE",
        bank_code="057",
        bank_name="Zenith Bank",
        is_valid=True,
        recipient_code="RCP_0987654321",
    )
    second_account = bank_service.add_bank_account(farmer.id, second_request, second_verification)
    bank_service.set_primary_bank_account(farmer.id, second_account.id)
    accounts = bank_service.get_bank_accounts(farmer.id)
    assert any(acc.id == second_account.id and acc.is_primary for acc in accounts)

    withdrawal_service = WithdrawalService(db_session, wallet_service)
    request = WithdrawalRequestCreate(amount=600.0, bank_account_id=second_account.id, idempotency_key="withdraw-1")
    withdrawal = withdrawal_service.create_withdrawal_request(farmer.id, request)

    assert withdrawal.status == WithdrawalStatus.COMPLETED
    assert withdrawal.fee > 0
    db_session.refresh(wallet)
    assert wallet.balance == pytest.approx(900.0)

    duplicate = withdrawal_service.create_withdrawal_request(farmer.id, request)
    assert duplicate.id == withdrawal.id
