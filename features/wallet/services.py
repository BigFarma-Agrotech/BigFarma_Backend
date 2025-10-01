"""
Wallet services containing business logic for wallet operations
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import logging
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, desc

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
    calculate_wallet_stats
)

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
        wallet.last_transaction_at = datetime.utcnow()
        
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
        wallet.last_transaction_at = datetime.utcnow()
        
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
        all_transactions = self.db.query(Transaction)\
            .filter(Transaction.wallet_id == wallet.id)\
            .all()
        
        stats = calculate_wallet_stats(all_transactions)
        
        return {
            "wallet": wallet,
            "recent_transactions": recent_transactions,
            "pending_withdrawals": pending_withdrawals,
            "total_earnings": stats["total_earnings"],
            "total_withdrawals": stats["total_withdrawals"]
        }


class WithdrawalService:
    """Service for withdrawal operations"""
    
    def __init__(self, db: Session, wallet_service: WalletService):
        self.db = db
        self.wallet_service = wallet_service
    
    def create_withdrawal_request(
        self,
        farmer_id: int,
        request_data: WithdrawalRequestCreate
    ) -> WithdrawalRequest:
        """
        Create a new withdrawal request
        
        Args:
            farmer_id: ID of the farmer
            request_data: Withdrawal request data
        
        Returns:
            Created withdrawal request
        
        Raises:
            Various exceptions for validation failures
        """
        # Get wallet
        wallet = self.wallet_service.get_wallet_by_farmer_id(farmer_id)
        
        # Check for pending withdrawals
        pending_count = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.wallet_id == wallet.id,
            WithdrawalRequest.status.in_([WithdrawalStatus.PENDING, WithdrawalStatus.PROCESSING])
        ).count()
        
        if pending_count > 0:
            raise PendingWithdrawalError()
        
        # Validate withdrawal amount
        is_valid, error_msg = validate_withdrawal_amount(
            request_data.amount,
            wallet.ledger_balance
        )
        if not is_valid:
            raise WithdrawalLimitError(error_msg)
        
        # Get bank account
        bank_account = self.db.query(BankAccount).filter(
            BankAccount.id == request_data.bank_account_id,
            BankAccount.wallet_id == wallet.id,
            BankAccount.is_active == True
        ).first()
        
        if not bank_account:
            raise BankAccountNotFoundError(str(request_data.bank_account_id))
        
        if bank_account.status != BankAccountStatus.VERIFIED:
            raise BankAccountVerificationError("Bank account must be verified before withdrawal")
        
        # Check idempotency
        if request_data.idempotency_key:
            existing = self.db.query(WithdrawalRequest).filter(
                WithdrawalRequest.idempotency_key == request_data.idempotency_key
            ).first()
            
            if existing:
                return existing  # Return existing request instead of creating duplicate
        
        # Calculate fee
        fee = calculate_withdrawal_fee(request_data.amount)
        final_amount = round_down_to_kobo(request_data.amount - fee)
        
        # Create withdrawal request
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
        
        logger.info(f"Created withdrawal request {withdrawal.reference} for {format_currency(request_data.amount)}")
        
        # Process withdrawal asynchronously (would typically use Celery or similar)
        # For now, we'll just mark it as processing
        self._process_withdrawal(withdrawal)
        
        return withdrawal
    
    def _process_withdrawal(self, withdrawal: WithdrawalRequest) -> None:
        """
        Process a withdrawal request (internal method)
        
        Args:
            withdrawal: Withdrawal request to process
        """
        try:
            # Update status to processing
            withdrawal.status = WithdrawalStatus.PROCESSING
            withdrawal.processed_at = datetime.utcnow()
            self.db.commit()
            
            # Here you would integrate with payment gateway
            # For now, we'll simulate success
            
            # Debit wallet
            transaction = self.wallet_service.debit_wallet(
                wallet_id=withdrawal.wallet_id,
                amount=withdrawal.amount,
                category=TransactionCategory.WITHDRAWAL,
                description=f"Withdrawal to {withdrawal.bank_account.bank_name} - {withdrawal.bank_account.account_number[-4:]}",
                withdrawal_request_id=withdrawal.id
            )
            
            # Update withdrawal status
            withdrawal.status = WithdrawalStatus.COMPLETED
            withdrawal.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Completed withdrawal {withdrawal.reference}")
            
        except Exception as e:
            logger.error(f"Failed to process withdrawal {withdrawal.reference}: {str(e)}")
            withdrawal.status = WithdrawalStatus.FAILED
            withdrawal.failed_at = datetime.utcnow()
            withdrawal.failure_reason = str(e)
            self.db.commit()
    
    def get_withdrawal_status(self, withdrawal_id: UUID) -> WithdrawalRequest:
        """
        Get withdrawal request status
        
        Args:
            withdrawal_id: UUID of the withdrawal request
        
        Returns:
            Withdrawal request object
        """
        withdrawal = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.id == withdrawal_id
        ).first()
        
        if not withdrawal:
            raise ValueError(f"Withdrawal request {withdrawal_id} not found")
        
        return withdrawal
    
    def cancel_withdrawal(self, withdrawal_id: UUID, farmer_id: int) -> WithdrawalRequest:
        """
        Cancel a pending withdrawal request
        
        Args:
            withdrawal_id: UUID of the withdrawal request
            farmer_id: ID of the farmer (for authorization)
        
        Returns:
            Updated withdrawal request
        """
        # Get wallet first to verify ownership
        wallet = self.wallet_service.get_wallet_by_farmer_id(farmer_id)
        
        withdrawal = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.id == withdrawal_id,
            WithdrawalRequest.wallet_id == wallet.id
        ).first()
        
        if not withdrawal:
            raise ValueError(f"Withdrawal request {withdrawal_id} not found")
        
        if withdrawal.status not in [WithdrawalStatus.PENDING]:
            raise ValueError(f"Cannot cancel withdrawal with status {withdrawal.status}")
        
        withdrawal.status = WithdrawalStatus.CANCELLED
        withdrawal.failed_at = datetime.utcnow()
        withdrawal.failure_reason = "Cancelled by user"
        
        self.db.commit()
        self.db.refresh(withdrawal)
        
        logger.info(f"Cancelled withdrawal {withdrawal.reference}")
        return withdrawal


class BankVerificationService:
    """Service for bank account verification"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def verify_bank_account(
        self,
        account_number: str,
        bank_code: str
    ) -> BankAccountVerifyResponse:
        """
        Verify bank account details with payment gateway
        
        Args:
            account_number: Bank account number
            bank_code: Bank code
        
        Returns:
            Verification response
        """
        # This would integrate with actual payment gateway
        # For now, we'll simulate the response
        
        # Simulate API delay
        import asyncio
        await asyncio.sleep(1)
        
        # Mock response - in production, this would call actual API
        mock_banks = {
            "058": "Guaranty Trust Bank",
            "033": "United Bank for Africa",
            "011": "First Bank of Nigeria",
            "214": "First City Monument Bank",
            "057": "Zenith Bank",
            "035": "Wema Bank",
            "044": "Access Bank"
        }
        
        bank_name = mock_banks.get(bank_code, "Unknown Bank")
        
        # Simulate verification success (in production, would check actual response)
        return BankAccountVerifyResponse(
            account_number=account_number,
            account_name="JOHN DOE",  # This would come from actual API
            bank_code=bank_code,
            bank_name=bank_name,
            is_valid=True,
            recipient_code=f"RCP_{account_number}_{bank_code}"
        )
    
    def add_bank_account(
        self,
        farmer_id: int,
        account_data: BankAccountCreateRequest,
        verification_response: BankAccountVerifyResponse
    ) -> BankAccount:
        """
        Add a verified bank account to farmer's wallet
        
        Args:
            farmer_id: ID of the farmer
            account_data: Bank account data
            verification_response: Verification response from gateway
        
        Returns:
            Created bank account
        """
        # Get wallet
        wallet_service = WalletService(self.db)
        wallet = wallet_service.get_wallet_by_farmer_id(farmer_id)
        
        # Check for duplicate
        existing = self.db.query(BankAccount).filter(
            BankAccount.wallet_id == wallet.id,
            BankAccount.account_number == account_data.account_number,
            BankAccount.bank_code == account_data.bank_code
        ).first()
        
        if existing:
            if existing.is_active:
                raise DuplicateBankAccountError(
                    account_data.account_number,
                    verification_response.bank_name
                )
            else:
                # Reactivate existing account
                existing.is_active = True
                existing.status = BankAccountStatus.VERIFIED
                existing.verified_at = datetime.utcnow()
                self.db.commit()
                return existing
        
        # Create new bank account
        bank_account = BankAccount(
            wallet_id=wallet.id,
            account_number=verification_response.account_number,
            account_name=verification_response.account_name,
            bank_code=verification_response.bank_code,
            bank_name=verification_response.bank_name,
            status=BankAccountStatus.VERIFIED,
            verified_at=datetime.utcnow(),
            verification_reference=generate_transaction_reference("VRF"),
            recipient_code=verification_response.recipient_code
        )
        
        # If this is the first account, make it primary
        if self.db.query(BankAccount).filter(
            BankAccount.wallet_id == wallet.id,
            BankAccount.is_active == True
        ).count() == 0:
            bank_account.is_primary = True
        
        self.db.add(bank_account)
        self.db.commit()
        self.db.refresh(bank_account)
        
        logger.info(f"Added bank account for farmer {farmer_id}")
        return bank_account
    
    def get_bank_accounts(self, farmer_id: int) -> List[BankAccount]:
        """
        Get all bank accounts for a farmer
        
        Args:
            farmer_id: ID of the farmer
        
        Returns:
            List of bank accounts
        """
        wallet_service = WalletService(self.db)
        wallet = wallet_service.get_wallet_by_farmer_id(farmer_id)
        
        return self.db.query(BankAccount).filter(
            BankAccount.wallet_id == wallet.id,
            BankAccount.is_active == True
        ).all()
    
    def set_primary_bank_account(self, farmer_id: int, account_id: UUID) -> BankAccount:
        """
        Set a bank account as primary
        
        Args:
            farmer_id: ID of the farmer
            account_id: UUID of the bank account
        
        Returns:
            Updated bank account
        """
        wallet_service = WalletService(self.db)
        wallet = wallet_service.get_wallet_by_farmer_id(farmer_id)
        
        # Get the account
        account = self.db.query(BankAccount).filter(
            BankAccount.id == account_id,
            BankAccount.wallet_id == wallet.id,
            BankAccount.is_active == True
        ).first()
        
        if not account:
            raise BankAccountNotFoundError(str(account_id))
        
        # Remove primary flag from all other accounts
        self.db.query(BankAccount).filter(
            BankAccount.wallet_id == wallet.id,
            BankAccount.id != account_id
        ).update({"is_primary": False})
        
        # Set this account as primary
        account.is_primary = True
        self.db.commit()
        self.db.refresh(account)
        
        return account
