"""
Wallet services containing business logic for wallet operations
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from uuid import UUID
import logging
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, desc, func

from features.auth.models import User
from .models import Wallet, Transaction, WithdrawalRequest, BankAccount, TransactionType, TransactionCategory, WithdrawalStatus, BankAccountStatus
from .schemas import (
    WalletResponse, TransactionResponse, WithdrawalRequestCreate,
    BankAccountCreateRequest, BankAccountVerifyResponse, TransactionFilter
)
from .exceptions import (
    WalletNotFoundError, InsufficientFundsError, WithdrawalLimitError,
    DuplicateWithdrawalError, PendingWithdrawalError, BankAccountNotFoundError,
    BankAccountVerificationError, DuplicateBankAccountError, TransactionError,
    PaymentGatewayError
)
from .utils import (
    generate_transaction_reference, calculate_withdrawal_fee,
    validate_withdrawal_amount, format_currency, round_down_to_kobo,
    calculate_wallet_stats, mask_account_number
)
from .config import wallet_config
from features.payments import paystack

logger = logging.getLogger(__name__)


class WalletService:
    """Service for wallet operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_wallet(self, farmer_id: int) -> Wallet:
        """
        Create a new wallet for a farmer
        
        Args:
            farmer_id: ID of the farmer
        
        Returns:
            Created wallet object
        """
        try:
            wallet = Wallet(
                farmer_id=farmer_id,
                balance=0.0,
                ledger_balance=0.0,
                currency="NGN"
            )
            self.db.add(wallet)
            self.db.commit()
            self.db.refresh(wallet)
            
            logger.info(f"Created wallet for farmer {farmer_id}")
            return wallet
            
        except IntegrityError:
            self.db.rollback()
            # Wallet already exists
            return self.get_wallet_by_farmer_id(farmer_id)
    
    def get_wallet_by_farmer_id(self, farmer_id: int) -> Wallet:
        """
        Get wallet by farmer ID
        
        Args:
            farmer_id: ID of the farmer
        
        Returns:
            Wallet object
        
        Raises:
            WalletNotFoundError: If wallet not found
        """
        wallet = self.db.query(Wallet).filter(
            Wallet.farmer_id == farmer_id,
            Wallet.is_active == True
        ).first()
        
        if not wallet:
            raise WalletNotFoundError(str(farmer_id))
        
        return wallet
    
    def get_wallet_balance(self, farmer_id: int) -> Dict[str, Any]:
        """
        Get wallet balance information
        
        Args:
            farmer_id: ID of the farmer
        
        Returns:
            Dictionary with balance information
        """
        wallet = self.get_wallet_by_farmer_id(farmer_id)
        
        return {
            "balance": wallet.balance,
            "ledger_balance": wallet.ledger_balance,
            "currency": wallet.currency,
            "formatted_balance": format_currency(wallet.balance),
            "formatted_ledger_balance": format_currency(wallet.ledger_balance),
            "last_transaction_at": wallet.last_transaction_at
        }
    
    def credit_wallet(
        self,
        wallet_id: UUID,
        amount: float,
        category: TransactionCategory,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
        product_order_id: Optional[UUID] = None,
        investment_id: Optional[UUID] = None
    ) -> Transaction:
        """
        Credit a wallet with funds
        
        Args:
            wallet_id: UUID of the wallet
            amount: Amount to credit
            category: Transaction category
            description: Transaction description
            metadata: Additional transaction metadata
            product_order_id: Related product order ID
            investment_id: Related investment ID
        
        Returns:
            Created transaction
        """

        query = self.db.query(Wallet).filter(Wallet.id == wallet_id)
        if self.db.bind and self.db.bind.dialect.name != "sqlite":
            query = query.with_for_update()
        wallet = query.first()
        
        if not wallet:
            raise WalletNotFoundError(str(wallet_id))
        
        # Record balances before transaction
        balance_before = wallet.balance
        
        # Update balances
        wallet.balance += amount
        wallet.ledger_balance += amount
        wallet.last_transaction_at = datetime.now(timezone.utc)
        
        # Create transaction record
        transaction = Transaction(
            wallet_id=wallet_id,
            reference=generate_transaction_reference("CRD"),
            type=TransactionType.CREDIT,
            category=category,
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            description=description,
            metadata_json=json.dumps(metadata) if metadata else None,
            product_order_id=product_order_id,
            investment_id=investment_id
        )
        
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        
        logger.info(f"Credited wallet {wallet_id} with {format_currency(amount)}")
        return transaction
    
    def debit_wallet(
        self,
        wallet_id: UUID,
        amount: float,
        category: TransactionCategory,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
        withdrawal_request_id: Optional[UUID] = None
    ) -> Transaction:
        """
        Debit funds from a wallet
        
        Args:
            wallet_id: UUID of the wallet
            amount: Amount to debit
            category: Transaction category
            description: Transaction description
            metadata: Additional transaction metadata
            withdrawal_request_id: Related withdrawal request ID
        
        Returns:
            Created transaction
        
        Raises:
            InsufficientFundsError: If wallet has insufficient funds
        """

        query = self.db.query(Wallet).filter(Wallet.id == wallet_id)
        if self.db.bind and self.db.bind.dialect.name != "sqlite":
            query = query.with_for_update()
        wallet = query.first()
        
        if not wallet:
            raise WalletNotFoundError(str(wallet_id))
        
        # Check sufficient funds
        if wallet.ledger_balance < amount:
            raise InsufficientFundsError(wallet.ledger_balance, amount)
        
        # Record balances before transaction
        balance_before = wallet.balance
        
        # Update balances
        wallet.balance -= amount
        wallet.ledger_balance -= amount
        wallet.last_transaction_at = datetime.now(timezone.utc)
        
        # Create transaction record
        transaction = Transaction(
            wallet_id=wallet_id,
            reference=generate_transaction_reference("DBT"),
            type=TransactionType.DEBIT,
            category=category,
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            description=description,
            metadata_json=json.dumps(metadata) if metadata else None,
            withdrawal_request_id=withdrawal_request_id
        )
        
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        
        logger.info(f"Debited wallet {wallet_id} with {format_currency(amount)}")
        return transaction
    
    def get_transaction_history(
        self,
        farmer_id: int,
        filter_params: TransactionFilter
    ) -> Dict[str, Any]:
        """
        Get paginated transaction history
        
        Args:
            farmer_id: ID of the farmer
            filter_params: Transaction filter parameters
        
        Returns:
            Dictionary with transactions and pagination info
        """
        wallet = self.get_wallet_by_farmer_id(farmer_id)
        
        # Base query
        query = self.db.query(Transaction).filter(
            Transaction.wallet_id == wallet.id
        )
        
        # Apply filters
        if filter_params.type:
            type_value = filter_params.type.value if hasattr(filter_params.type, "value") else filter_params.type
            query = query.filter(Transaction.type == TransactionType(type_value))

        if filter_params.category:
            category_value = filter_params.category.value if hasattr(filter_params.category, "value") else filter_params.category
            query = query.filter(Transaction.category == TransactionCategory(category_value))

        if filter_params.start_date:
            query = query.filter(Transaction.created_at >= filter_params.start_date)
        
        if filter_params.end_date:
            query = query.filter(Transaction.created_at <= filter_params.end_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (filter_params.page - 1) * filter_params.limit
        transactions = query.order_by(desc(Transaction.created_at))\
            .offset(offset)\
            .limit(filter_params.limit)\
            .all()
        
        # Check if there's next page
        has_next = total > (filter_params.page * filter_params.limit)
        
        return {
            "transactions": transactions,
            "total": total,
            "page": filter_params.page,
            "limit": filter_params.limit,
            "has_next": has_next
        }
    
    def get_wallet_dashboard(self, farmer_id: int) -> Dict[str, Any]:
        """
        Get comprehensive wallet dashboard data
        
        Args:
            farmer_id: ID of the farmer
        
        Returns:
            Dictionary with wallet dashboard information
        """
        wallet = self.get_wallet_by_farmer_id(farmer_id)
        
        # Get recent transactions
        recent_transactions = self.db.query(Transaction)\
            .filter(Transaction.wallet_id == wallet.id)\
            .order_by(desc(Transaction.created_at))\
            .limit(10)\
            .all()
        
        # Get pending withdrawals
        pending_withdrawals = self.db.query(WithdrawalRequest)\
            .filter(
                WithdrawalRequest.wallet_id == wallet.id,
                WithdrawalRequest.status.in_([WithdrawalStatus.PENDING, WithdrawalStatus.PROCESSING])
            )\
            .all()
        
        # Calculate stats
        # One summed row per (type, category) instead of loading every transaction
        all_transactions = self.db.query(
            Transaction.type, Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
        ).filter(Transaction.wallet_id == wallet.id).group_by(Transaction.type, Transaction.category).all()
        
        stats = calculate_wallet_stats(all_transactions)
        
        return {
            "wallet": wallet,
            "recent_transactions": recent_transactions,
            "pending_withdrawals": pending_withdrawals,
            "total_earnings": stats["total_earnings"],
            "total_withdrawals": stats["total_withdrawals"]
        }


# Paystack's transfer statuses that mean "accepted, final result comes by webhook"
TRANSFER_IN_FLIGHT = {"pending", "received", "processing", "queued"}
OPEN_WITHDRAWAL_STATUSES = [WithdrawalStatus.PENDING, WithdrawalStatus.PROCESSING]

GATEWAY_UNAVAILABLE = "Withdrawals are temporarily unavailable. Please try again later."


def _to_kobo(amount: float) -> int:
    return int(round(amount * 100))


class WithdrawalService:
    """Withdrawals: hold the money in the wallet, send it with a Paystack transfer,
    and settle (or refund) when Paystack reports the result."""

    def __init__(self, db: Session, wallet_service: WalletService):
        self.db = db
        self.wallet_service = wallet_service

    async def create_withdrawal_request(
        self,
        farmer_id: int,
        request_data: WithdrawalRequestCreate
    ) -> WithdrawalRequest:
        """Debit the wallet and start a transfer to one of the farmer's bank accounts."""
        wallet = self.wallet_service.get_wallet_by_farmer_id(farmer_id)

        # A retried request (same key) gets the original withdrawal back
        if request_data.idempotency_key:
            existing = self.db.query(WithdrawalRequest).filter(
                WithdrawalRequest.idempotency_key == request_data.idempotency_key,
                WithdrawalRequest.wallet_id == wallet.id,
            ).first()
            if existing:
                return existing

        pending_count = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.wallet_id == wallet.id,
            WithdrawalRequest.status.in_(OPEN_WITHDRAWAL_STATUSES)
        ).count()
        if pending_count > 0:
            raise PendingWithdrawalError()

        if request_data.amount > wallet.ledger_balance:
            raise InsufficientFundsError(wallet.ledger_balance, request_data.amount)
        is_valid, error_msg = validate_withdrawal_amount(
            request_data.amount, wallet.ledger_balance, wallet_config.MINIMUM_WITHDRAWAL_AMOUNT
        )
        if not is_valid:
            raise WithdrawalLimitError(error_msg)

        bank_account = self.db.query(BankAccount).filter(
            BankAccount.id == request_data.bank_account_id,
            BankAccount.wallet_id == wallet.id,
            BankAccount.is_active == True
        ).first()
        if not bank_account:
            raise BankAccountNotFoundError(str(request_data.bank_account_id))
        if bank_account.status != BankAccountStatus.VERIFIED or not bank_account.recipient_code:
            raise BankAccountVerificationError(
                "This bank account isn't ready for withdrawals. Remove it and add it again."
            )

        fee = round_down_to_kobo(calculate_withdrawal_fee(
            request_data.amount, wallet_config.WITHDRAWAL_FEE_PERCENTAGE, wallet_config.MAXIMUM_WITHDRAWAL_FEE
        ))
        final_amount = round_down_to_kobo(request_data.amount - fee)

        withdrawal = WithdrawalRequest(
            wallet_id=wallet.id,
            bank_account_id=bank_account.id,
            amount=request_data.amount,
            fee=fee,
            final_amount=final_amount,
            reference=generate_transaction_reference("WDR"),
            status=WithdrawalStatus.PENDING,
            idempotency_key=request_data.idempotency_key
        )
        self.db.add(withdrawal)
        self.db.commit()
        self.db.refresh(withdrawal)

        # Hold the money first so it can't be withdrawn twice while the transfer runs
        try:
            self.wallet_service.debit_wallet(
                wallet_id=wallet.id,
                amount=withdrawal.amount,
                category=TransactionCategory.WITHDRAWAL,
                description=f"Withdrawal to {bank_account.bank_name} - {mask_account_number(bank_account.account_number)}",
                withdrawal_request_id=withdrawal.id,
            )
        except InsufficientFundsError:
            self._mark_failed(withdrawal, "Insufficient funds")
            self.db.commit()
            raise
        self._set_transaction_status(withdrawal, "pending")
        self.db.commit()

        logger.info(f"Created withdrawal request {withdrawal.reference} for {format_currency(withdrawal.amount)}")
        await self._send_transfer(withdrawal)
        self.db.refresh(withdrawal)
        return withdrawal

    async def _send_transfer(self, withdrawal: WithdrawalRequest) -> None:
        """Ask Paystack to pay out; failures put the money back in the wallet."""
        bank_account = withdrawal.bank_account
        withdrawal.status = WithdrawalStatus.PROCESSING
        withdrawal.processed_at = datetime.now(timezone.utc)
        self.db.commit()

        try:
            transfer = await paystack.initiate_transfer(
                amount_kobo=_to_kobo(withdrawal.final_amount),
                recipient_code=bank_account.recipient_code,
                reference=withdrawal.reference,
                reason="BigFarma wallet withdrawal",
            )
        except paystack.PaystackError as exc:
            logger.error(f"Transfer for withdrawal {withdrawal.reference} failed to start: {exc.message}")
            self._fail_and_refund(withdrawal, exc.message)
            raise PaymentGatewayError(
                GATEWAY_UNAVAILABLE if exc.status_code == 503
                else "We couldn't send your withdrawal. Your money is back in your wallet; please try again."
            )

        withdrawal.gateway_reference = transfer.get("transfer_code")
        withdrawal.gateway_response = json.dumps(transfer, default=str)[:4000]
        status = str(transfer.get("status") or "").lower()

        if status == "success":
            self._mark_completed(withdrawal)
        elif status in TRANSFER_IN_FLIGHT:
            pass  # stays PROCESSING until the transfer.success / transfer.failed webhook
        else:
            # "otp" means OTP for transfers is still switched on in the Paystack dashboard
            logger.error(f"Transfer for withdrawal {withdrawal.reference} came back '{status}'")
            self._fail_and_refund(withdrawal, f"Transfer {status or 'rejected'}")
            raise PaymentGatewayError(GATEWAY_UNAVAILABLE)
        self.db.commit()

    def apply_transfer_event(self, event: str, data: Dict[str, Any]) -> Optional[WithdrawalRequest]:
        """Settle a withdrawal from a Paystack transfer.* webhook. Safe to receive twice."""
        reference = data.get("reference")
        withdrawal = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.reference == reference
        ).first() if reference else None
        if not withdrawal:
            logger.warning(f"Transfer webhook for unknown reference {reference}")
            return None

        withdrawal.gateway_response = json.dumps(data, default=str)[:4000]
        if event == "transfer.success" and withdrawal.status in OPEN_WITHDRAWAL_STATUSES:
            self._mark_completed(withdrawal)
        elif event == "transfer.failed" and withdrawal.status in OPEN_WITHDRAWAL_STATUSES:
            self._fail_and_refund(withdrawal, data.get("reason") or "Transfer failed")
        elif event == "transfer.reversed" and withdrawal.status in OPEN_WITHDRAWAL_STATUSES + [WithdrawalStatus.COMPLETED]:
            self._fail_and_refund(withdrawal, "Transfer reversed by the bank")
        self.db.commit()
        self.db.refresh(withdrawal)
        return withdrawal

    def _set_transaction_status(self, withdrawal: WithdrawalRequest, status: str) -> None:
        self.db.query(Transaction).filter(
            Transaction.withdrawal_request_id == withdrawal.id,
            Transaction.type == TransactionType.DEBIT,
        ).update({"status": status})

    def _mark_completed(self, withdrawal: WithdrawalRequest) -> None:
        withdrawal.status = WithdrawalStatus.COMPLETED
        withdrawal.completed_at = datetime.now(timezone.utc)
        self._set_transaction_status(withdrawal, "completed")
        logger.info(f"Completed withdrawal {withdrawal.reference}")

    def _mark_failed(self, withdrawal: WithdrawalRequest, reason: str,
                     status: WithdrawalStatus = WithdrawalStatus.FAILED) -> None:
        withdrawal.status = status
        withdrawal.failed_at = datetime.now(timezone.utc)
        withdrawal.failure_reason = reason

    def _fail_and_refund(self, withdrawal: WithdrawalRequest, reason: str,
                         status: WithdrawalStatus = WithdrawalStatus.FAILED) -> None:
        """Mark the withdrawal failed and credit the held amount back to the wallet."""
        self._mark_failed(withdrawal, reason, status)
        self._set_transaction_status(withdrawal, "reversed")
        # credit_wallet commits, which also saves the status change above
        self.wallet_service.credit_wallet(
            wallet_id=withdrawal.wallet_id,
            amount=withdrawal.amount,
            category=TransactionCategory.REFUND,
            description=f"Withdrawal {withdrawal.reference} returned to wallet",
            metadata={"withdrawal_reference": withdrawal.reference, "reason": reason},
        )
        logger.info(f"Refunded withdrawal {withdrawal.reference}: {reason}")

    def get_withdrawal_status(self, withdrawal_id: UUID) -> WithdrawalRequest:
        withdrawal = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.id == withdrawal_id
        ).first()
        if not withdrawal:
            raise ValueError(f"Withdrawal request {withdrawal_id} not found")
        return withdrawal

    def cancel_withdrawal(self, withdrawal_id: UUID, farmer_id: int) -> WithdrawalRequest:
        """Cancel a withdrawal that hasn't been sent to the bank yet; the money goes back to the wallet."""
        wallet = self.wallet_service.get_wallet_by_farmer_id(farmer_id)
        withdrawal = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.id == withdrawal_id,
            WithdrawalRequest.wallet_id == wallet.id
        ).first()
        if not withdrawal:
            raise ValueError(f"Withdrawal request {withdrawal_id} not found")
        if withdrawal.status != WithdrawalStatus.PENDING:
            raise ValueError("This withdrawal has already been sent to your bank and can't be cancelled")

        held = self.db.query(Transaction).filter(Transaction.withdrawal_request_id == withdrawal.id).count() > 0
        if held:
            self._fail_and_refund(withdrawal, "Cancelled by user", WithdrawalStatus.CANCELLED)
        else:
            self._mark_failed(withdrawal, "Cancelled by user", WithdrawalStatus.CANCELLED)
            self.db.commit()
        self.db.refresh(withdrawal)
        logger.info(f"Cancelled withdrawal {withdrawal.reference}")
        return withdrawal


# Paystack's bank list changes rarely; keep it for a day
_BANKS_CACHE: Dict[str, Any] = {"banks": None, "fetched_at": None}
# Paystack's test-mode bank: resolves any number, with no daily limit
TEST_BANK = {"name": "Test Bank (test mode only)", "code": "001"}
TEST_MODE_LIMIT = ("Paystack test mode only allows 3 checks of real bank accounts a day. "
                   "Use Test Bank, or switch the server to a live Paystack key.")
TOO_MANY_CHECKS = "Too many account checks right now. Please try again in a few minutes."
BANKS_CACHE_TTL = timedelta(hours=24)


class BankVerificationService:
    """Bank accounts farmers withdraw to, checked and registered with Paystack."""

    def __init__(self, db: Session):
        self.db = db

    async def list_banks(self) -> List[Dict[str, str]]:
        """Nigerian banks that accept transfers: [{name, code}] sorted by name, plus
        Paystack's Test Bank when running on a test key."""
        banks = await self._paystack_banks()
        return [TEST_BANK, *banks] if paystack.is_test_mode() else banks

    async def _paystack_banks(self) -> List[Dict[str, str]]:
        fetched_at = _BANKS_CACHE["fetched_at"]
        if _BANKS_CACHE["banks"] and fetched_at and datetime.now(timezone.utc) - fetched_at < BANKS_CACHE_TTL:
            return _BANKS_CACHE["banks"]
        try:
            raw = await paystack.list_banks()
        except paystack.PaystackError as exc:
            if _BANKS_CACHE["banks"]:
                return _BANKS_CACHE["banks"]  # stale beats nothing
            raise PaymentGatewayError(GATEWAY_UNAVAILABLE if exc.status_code == 503 else exc.message)

        banks: Dict[str, Dict[str, str]] = {}
        for bank in raw if isinstance(raw, list) else []:
            code = str(bank.get("code") or "").strip()
            if not code or not bank.get("active", True) or bank.get("is_deleted"):
                continue
            if bank.get("type") not in (None, "nuban"):
                continue
            banks.setdefault(code, {"name": str(bank.get("name") or code).strip(), "code": code})
        result = sorted(banks.values(), key=lambda b: b["name"].lower())
        if result:
            _BANKS_CACHE.update(banks=result, fetched_at=datetime.now(timezone.utc))
        return result

    async def verify_bank_account(self, account_number: str, bank_code: str) -> BankAccountVerifyResponse:
        """Look up the name on the account with Paystack."""
        banks = {bank["code"]: bank["name"] for bank in await self.list_banks()}
        if bank_code not in banks:
            raise BankAccountVerificationError("Choose your bank from the list.")
        not_found = f"We couldn't find account {account_number} at {banks[bank_code]}. Check the number and bank."
        try:
            resolved = await paystack.resolve_account(account_number, bank_code)
        except paystack.PaystackError as exc:
            # Only a refusal about this account means it wasn't found; limits and
            # outages aren't the farmer's mistake, so say what actually happened
            if exc.upstream_status == 429:
                logger.warning("Paystack account lookup rate-limited: %s", exc.message)
                raise PaymentGatewayError(TEST_MODE_LIMIT if paystack.is_test_mode() else TOO_MANY_CHECKS)
            if exc.status_code == 503 or exc.upstream_status is None or exc.upstream_status >= 500:
                raise PaymentGatewayError(GATEWAY_UNAVAILABLE)
            raise BankAccountVerificationError(not_found)
        account_name = str(resolved.get("account_name") or "").strip()
        if not account_name:
            raise BankAccountVerificationError(not_found)
        return BankAccountVerifyResponse(
            account_number=account_number,
            account_name=account_name,
            bank_code=bank_code,
            bank_name=banks[bank_code],
            is_valid=True,
        )

    async def register_recipient(self, verification: BankAccountVerifyResponse) -> BankAccountVerifyResponse:
        """Create the Paystack transfer recipient that withdrawals are sent to."""
        try:
            recipient = await paystack.create_transfer_recipient(
                verification.account_name, verification.account_number, verification.bank_code
            )
        except paystack.PaystackError as exc:
            raise PaymentGatewayError(GATEWAY_UNAVAILABLE if exc.status_code == 503 else exc.message)
        if not recipient.get("recipient_code"):
            raise PaymentGatewayError(GATEWAY_UNAVAILABLE)
        return verification.model_copy(update={"recipient_code": recipient["recipient_code"]})

    def add_bank_account(
        self,
        farmer_id: int,
        account_data: BankAccountCreateRequest,
        verification_response: BankAccountVerifyResponse
    ) -> BankAccount:
        """Save a verified bank account; the first one becomes the primary account."""
        wallet = WalletService(self.db).get_wallet_by_farmer_id(farmer_id)

        existing = self.db.query(BankAccount).filter(
            BankAccount.wallet_id == wallet.id,
            BankAccount.account_number == account_data.account_number,
            BankAccount.bank_code == account_data.bank_code
        ).first()
        if existing and existing.is_active:
            raise DuplicateBankAccountError(account_data.account_number, verification_response.bank_name)

        active_count = self.db.query(BankAccount).filter(
            BankAccount.wallet_id == wallet.id,
            BankAccount.is_active == True
        ).count()
        if active_count >= wallet_config.MAX_BANK_ACCOUNTS_PER_USER:
            raise BankAccountVerificationError(
                f"You can link up to {wallet_config.MAX_BANK_ACCOUNTS_PER_USER} bank accounts. Remove one first."
            )

        if existing:
            # Re-adding a removed account: refresh it with the latest details
            bank_account = existing
            bank_account.is_active = True
            bank_account.is_primary = False
        else:
            bank_account = BankAccount(wallet_id=wallet.id)
            self.db.add(bank_account)
        bank_account.account_number = verification_response.account_number
        bank_account.account_name = verification_response.account_name
        bank_account.bank_code = verification_response.bank_code
        bank_account.bank_name = verification_response.bank_name
        bank_account.status = BankAccountStatus.VERIFIED
        bank_account.verified_at = datetime.now(timezone.utc)
        bank_account.verification_reference = generate_transaction_reference("VRF")
        bank_account.recipient_code = verification_response.recipient_code
        bank_account.is_primary = active_count == 0

        self.db.commit()
        self.db.refresh(bank_account)
        logger.info(f"Added bank account for farmer {farmer_id}")
        return bank_account

    def get_bank_accounts(self, farmer_id: int) -> List[BankAccount]:
        """The farmer's linked accounts, primary first."""
        wallet = WalletService(self.db).get_wallet_by_farmer_id(farmer_id)
        return self.db.query(BankAccount).filter(
            BankAccount.wallet_id == wallet.id,
            BankAccount.is_active == True
        ).order_by(desc(BankAccount.is_primary), BankAccount.created_at).all()

    def _get_active_account(self, farmer_id: int, account_id: UUID) -> tuple:
        wallet = WalletService(self.db).get_wallet_by_farmer_id(farmer_id)
        account = self.db.query(BankAccount).filter(
            BankAccount.id == account_id,
            BankAccount.wallet_id == wallet.id,
            BankAccount.is_active == True
        ).first()
        if not account:
            raise BankAccountNotFoundError(str(account_id))
        return wallet, account

    def set_primary_bank_account(self, farmer_id: int, account_id: UUID) -> BankAccount:
        wallet, account = self._get_active_account(farmer_id, account_id)
        self.db.query(BankAccount).filter(
            BankAccount.wallet_id == wallet.id,
            BankAccount.id != account_id
        ).update({"is_primary": False})
        account.is_primary = True
        self.db.commit()
        self.db.refresh(account)
        return account

    def remove_bank_account(self, farmer_id: int, account_id: UUID) -> None:
        """Unlink an account (kept for withdrawal history). Another account becomes primary."""
        wallet, account = self._get_active_account(farmer_id, account_id)
        in_use = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.bank_account_id == account.id,
            WithdrawalRequest.status.in_(OPEN_WITHDRAWAL_STATUSES)
        ).count()
        if in_use:
            raise BankAccountVerificationError("A withdrawal to this account is still in progress.")

        was_primary = account.is_primary
        account.is_active = False
        account.is_primary = False
        if was_primary:
            replacement = self.db.query(BankAccount).filter(
                BankAccount.wallet_id == wallet.id,
                BankAccount.is_active == True,
                BankAccount.id != account.id
            ).order_by(BankAccount.created_at).first()
            if replacement:
                replacement.is_primary = True
        self.db.commit()
