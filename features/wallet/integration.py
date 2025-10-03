"""
Integration hooks for wallet service with other parts of the application
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from .exceptions import WalletNotFoundError
from .models import TransactionCategory
from .services import WalletService


class WalletIntegration:
    """Integration point for other services to interact with wallet"""

    @staticmethod
    def _get_or_create_wallet(db: Session, farmer_id: int):
        """Fetch wallet for farmer, creating one if necessary."""
        wallet_service = WalletService(db)
        try:
            return wallet_service.get_wallet_by_farmer_id(farmer_id)
        except WalletNotFoundError:
            return wallet_service.create_wallet(farmer_id)

    @staticmethod
    def credit_for_product_sale(
        db: Session,
        farmer_id: int,
        amount: float,
        product_name: str,
        order_id: int,
    ) -> bool:
        """Credit the farmer's wallet when a product sale completes."""
        try:
            wallet = WalletIntegration._get_or_create_wallet(db, farmer_id)
            wallet_service = WalletService(db)

            transaction = wallet_service.credit_wallet(
                wallet_id=wallet.id,
                amount=amount,
                category=TransactionCategory.PRODUCT_SALE,
                description=f"Sale of {product_name}",
                metadata={
                    "product_name": product_name,
                    "order_id": str(order_id),
                },
            )
            return transaction is not None
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to credit wallet for product sale: {exc}")
            return False

    @staticmethod
    def credit_for_investment_payout(
        db: Session,
        farmer_id: int,
        amount: float,
        investment_title: str,
        investment_id: int,
        payout_type: str = "returns",
    ) -> bool:
        """Credit the farmer's wallet for investment earnings."""
        try:
            wallet = WalletIntegration._get_or_create_wallet(db, farmer_id)
            wallet_service = WalletService(db)

            description = f"Investment {payout_type} from {investment_title}"
            transaction = wallet_service.credit_wallet(
                wallet_id=wallet.id,
                amount=amount,
                category=TransactionCategory.INVESTMENT_PAYOUT,
                description=description,
                metadata={
                    "investment_title": investment_title,
                    "investment_id": str(investment_id),
                    "payout_type": payout_type,
                },
            )
            return transaction is not None
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to credit wallet for investment payout: {exc}")
            return False

    @staticmethod
    def process_refund(
        db: Session,
        farmer_id: int,
        amount: float,
        reason: str,
        order_id: Optional[int] = None,
    ) -> bool:
        """Return funds to a farmer's wallet."""
        try:
            wallet = WalletIntegration._get_or_create_wallet(db, farmer_id)
            wallet_service = WalletService(db)

            transaction = wallet_service.credit_wallet(
                wallet_id=wallet.id,
                amount=amount,
                category=TransactionCategory.REFUND,
                description=f"Refund: {reason}",
                metadata={
                    "reason": reason,
                    "order_id": str(order_id) if order_id else None,
                },
            )
            return transaction is not None
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to process refund: {exc}")
            return False

    @staticmethod
    def get_farmer_balance(db: Session, farmer_id: int) -> Optional[float]:
        """Quick method to get farmer's wallet ledger balance."""
        try:
            wallet_service = WalletService(db)
            balance_info = wallet_service.get_wallet_balance(farmer_id)
            return balance_info["ledger_balance"]
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def can_afford_purchase(
        db: Session,
        farmer_id: int,
        amount: float,
    ) -> bool:
        """Check if farmer has enough ledger balance for a purchase."""
        balance = WalletIntegration.get_farmer_balance(db, farmer_id)
        return balance is not None and balance >= amount


class WalletEventHooks:
    """Event hooks that wallet service will call. Other services can implement these hooks."""

    @staticmethod
    def on_withdrawal_completed(withdrawal_request_id: UUID):
        pass

    @staticmethod
    def on_withdrawal_failed(withdrawal_request_id: UUID, reason: str):
        pass

    @staticmethod
    def on_large_transaction(transaction_id: UUID, amount: float):
        pass

    @staticmethod
    def on_wallet_created(wallet_id: UUID, farmer_id: UUID):
        pass
