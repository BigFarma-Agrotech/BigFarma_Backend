"""
Integration hooks for wallet service with other parts of the application
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from .services import WalletService
from .models import TransactionCategory


class WalletIntegration:
    """Integration point for other services to interact with wallet"""
    
    @staticmethod
    def credit_for_product_sale(
        db: Session,
        farmer_id: UUID,
        amount: float,
        product_name: str,
        order_id: UUID
    ) -> bool:
        """
        Credit farmer's wallet when a product is sold
        
        Args:
            db: Database session
            farmer_id: UUID of the farmer
            amount: Sale amount
            product_name: Name of the product sold
            order_id: UUID of the order
        
        Returns:
            True if successful, False otherwise
        """
        try:
            wallet_service = WalletService(db)
            wallet = wallet_service.get_wallet_by_farmer_id(farmer_id)
            
            transaction = wallet_service.credit_wallet(
                wallet_id=wallet.id,
                amount=amount,
                category=TransactionCategory.PRODUCT_SALE,
                description=f"Sale of {product_name}",
                metadata={
                    "product_name": product_name,
                    "order_id": str(order_id)
                },
                product_order_id=order_id
            )
            
            return transaction is not None
            
        except Exception as e:
            # Log error
            print(f"Failed to credit wallet for product sale: {str(e)}")
            return False
    
    @staticmethod
    def credit_for_investment_payout(
        db: Session,
        farmer_id: UUID,
        amount: float,
        investment_title: str,
        investment_id: UUID,
        payout_type: str = "returns"
    ) -> bool:
        """
        Credit farmer's wallet for investment payouts
        
        Args:
            db: Database session
            farmer_id: UUID of the farmer
            amount: Payout amount
            investment_title: Title of the investment
            investment_id: UUID of the investment
            payout_type: Type of payout (returns, principal, etc.)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            wallet_service = WalletService(db)
            wallet = wallet_service.get_wallet_by_farmer_id(farmer_id)
            
            description = f"Investment {payout_type} from {investment_title}"
            
            transaction = wallet_service.credit_wallet(
                wallet_id=wallet.id,
                amount=amount,
                category=TransactionCategory.INVESTMENT_PAYOUT,
                description=description,
                metadata={
                    "investment_title": investment_title,
                    "investment_id": str(investment_id),
                    "payout_type": payout_type
                },
                investment_id=investment_id
            )
            
            return transaction is not None
            
        except Exception as e:
            # Log error
            print(f"Failed to credit wallet for investment payout: {str(e)}")
            return False
    
    @staticmethod
    def process_refund(
        db: Session,
        farmer_id: UUID,
        amount: float,
        reason: str,
        order_id: Optional[UUID] = None
    ) -> bool:
        """
        Process a refund to farmer's wallet
        
        Args:
            db: Database session
            farmer_id: UUID of the farmer
            amount: Refund amount
            reason: Reason for refund
            order_id: Optional order ID related to refund
        
        Returns:
            True if successful, False otherwise
        """
        try:
            wallet_service = WalletService(db)
            wallet = wallet_service.get_wallet_by_farmer_id(farmer_id)
            
            transaction = wallet_service.credit_wallet(
                wallet_id=wallet.id,
                amount=amount,
                category=TransactionCategory.REFUND,
                description=f"Refund: {reason}",
                metadata={
                    "reason": reason,
                    "order_id": str(order_id) if order_id else None
                },
                product_order_id=order_id
            )
            
            return transaction is not None
            
        except Exception as e:
            # Log error
            print(f"Failed to process refund: {str(e)}")
            return False
    
    @staticmethod
    def get_farmer_balance(db: Session, farmer_id: UUID) -> Optional[float]:
        """
        Quick method to get farmer's wallet balance
        
        Args:
            db: Database session
            farmer_id: UUID of the farmer
        
        Returns:
            Wallet balance or None if error
        """
        try:
            wallet_service = WalletService(db)
            balance_info = wallet_service.get_wallet_balance(farmer_id)
            return balance_info["ledger_balance"]
        except:
            return None
    
    @staticmethod
    def can_afford_purchase(
        db: Session,
        farmer_id: UUID,
        amount: float
    ) -> bool:
        """
        Check if farmer can afford a purchase
        
        Args:
            db: Database session
            farmer_id: UUID of the farmer
            amount: Purchase amount
        
        Returns:
            True if farmer has sufficient balance
        """
        balance = WalletIntegration.get_farmer_balance(db, farmer_id)
        return balance is not None and balance >= amount


# Event hooks for other services to implement
class WalletEventHooks:
    """
    Event hooks that wallet service will call
    Other services can implement these hooks
    """
    
    @staticmethod
    def on_withdrawal_completed(withdrawal_request_id: UUID):
        """Called when a withdrawal is completed successfully"""
        # Send notification
        # Update analytics
        pass
    
    @staticmethod
    def on_withdrawal_failed(withdrawal_request_id: UUID, reason: str):
        """Called when a withdrawal fails"""
        # Send notification
        # Log failure
        pass
    
    @staticmethod
    def on_large_transaction(transaction_id: UUID, amount: float):
        """Called when a large transaction occurs (configurable threshold)"""
        # Flag for review
        # Send alert
        pass
    
    @staticmethod
    def on_wallet_created(wallet_id: UUID, farmer_id: UUID):
        """Called when a new wallet is created"""
        # Send welcome notification
        # Initialize analytics
        pass
