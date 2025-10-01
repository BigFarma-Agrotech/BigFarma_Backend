"""
Custom exceptions for wallet operations
"""


class WalletException(Exception):
    """Base exception for wallet operations"""
    def __init__(self, message: str, code: str = "wallet_error"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class WalletNotFoundError(WalletException):
    """Raised when wallet is not found"""
    def __init__(self, farmer_id: str):
        super().__init__(
            message=f"Wallet not found for farmer {farmer_id}",
            code="wallet_not_found"
        )


class InsufficientFundsError(WalletException):
    """Raised when wallet has insufficient funds"""
    def __init__(self, available: float, requested: float):
        super().__init__(
            message=f"Insufficient funds. Available: ₦{available:,.2f}, Requested: ₦{requested:,.2f}",
            code="insufficient_funds"
        )
        self.available = available
        self.requested = requested


class WithdrawalLimitError(WalletException):
    """Raised when withdrawal amount violates limits"""
    def __init__(self, message: str):
        super().__init__(message=message, code="withdrawal_limit_error")


class DuplicateWithdrawalError(WalletException):
    """Raised when there's an attempt to create duplicate withdrawal"""
    def __init__(self, idempotency_key: str):
        super().__init__(
            message=f"Duplicate withdrawal request with key: {idempotency_key}",
            code="duplicate_withdrawal"
        )


class PendingWithdrawalError(WalletException):
    """Raised when there's already a pending withdrawal"""
    def __init__(self):
        super().__init__(
            message="You have a pending withdrawal. Please wait until it is completed.",
            code="pending_withdrawal_exists"
        )


class BankAccountError(WalletException):
    """Base exception for bank account operations"""
    pass


class BankAccountNotFoundError(BankAccountError):
    """Raised when bank account is not found"""
    def __init__(self, account_id: str):
        super().__init__(
            message=f"Bank account {account_id} not found",
            code="bank_account_not_found"
        )


class BankAccountVerificationError(BankAccountError):
    """Raised when bank account verification fails"""
    def __init__(self, message: str = "We couldn't verify this account. Please try again."):
        super().__init__(message=message, code="bank_verification_failed")


class DuplicateBankAccountError(BankAccountError):
    """Raised when trying to add duplicate bank account"""
    def __init__(self, account_number: str, bank_name: str):
        super().__init__(
            message=f"Account {account_number} at {bank_name} already exists",
            code="duplicate_bank_account"
        )


class TransactionError(WalletException):
    """Base exception for transaction operations"""
    pass


class InvalidTransactionError(TransactionError):
    """Raised when transaction validation fails"""
    def __init__(self, message: str):
        super().__init__(message=message, code="invalid_transaction")


class TransactionProcessingError(TransactionError):
    """Raised when transaction processing fails"""
    def __init__(self, message: str = "Transaction processing failed. Please try again."):
        super().__init__(message=message, code="transaction_processing_failed")


class PaymentGatewayError(WalletException):
    """Raised when payment gateway operations fail"""
    def __init__(self, message: str = "Payment gateway error. Please try again later."):
        super().__init__(message=message, code="payment_gateway_error")


class NetworkError(WalletException):
    """Raised when network operations fail"""
    def __init__(self, message: str = "You're offline. We'll try again when your connection is back."):
        super().__init__(message=message, code="network_error")
