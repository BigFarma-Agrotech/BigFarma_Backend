"""
Utility functions for wallet operations
"""
import secrets
import string
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
from decimal import Decimal, ROUND_DOWN


def generate_transaction_reference(prefix: str = "TXN") -> str:
    """
    Generate a unique transaction reference
    
    Args:
        prefix: Prefix for the reference (TXN, WDR, etc.)
    
    Returns:
        Unique reference string
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{prefix}_{timestamp}_{random_suffix}"


def generate_idempotency_key() -> str:
    """Generate a unique idempotency key for withdrawal requests"""
    return secrets.token_urlsafe(32)


def format_currency(amount: float, currency: str = "NGN") -> str:
    """
    Format amount with currency symbol
    
    Args:
        amount: Amount to format
        currency: Currency code (default: NGN)
    
    Returns:
        Formatted currency string
    """
    currency_symbols = {
        "NGN": "₦",
        "USD": "$",
        "GBP": "£",
        "EUR": "€"
    }
    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"


def calculate_withdrawal_fee(amount: float, fee_percentage: float = 1.5, max_fee: float = 1000.0) -> float:
    """
    Calculate withdrawal fee
    
    Args:
        amount: Withdrawal amount
        fee_percentage: Fee percentage (default: 1.5%)
        max_fee: Maximum fee cap (default: ₦1000)
    
    Returns:
        Calculated fee amount
    """
    fee = (amount * fee_percentage) / 100
    return min(fee, max_fee)


def round_down_to_kobo(amount: float) -> float:
    """
    Round down amount to nearest kobo (2 decimal places)
    
    Args:
        amount: Amount to round
    
    Returns:
        Rounded amount
    """
    decimal_amount = Decimal(str(amount))
    return float(decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_DOWN))


def validate_withdrawal_amount(amount: float, balance: float, minimum: float = 500.0) -> tuple[bool, Optional[str]]:
    """
    Validate withdrawal amount against business rules
    
    Args:
        amount: Requested withdrawal amount
        balance: Available balance
        minimum: Minimum withdrawal amount
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if amount < minimum:
        return False, f"Minimum withdrawal amount is {format_currency(minimum)}"
    
    if amount > balance:
        return False, f"Insufficient funds. You need at least {format_currency(amount)} to withdraw."
    
    return True, None


def mask_account_number(account_number: str) -> str:
    """
    Mask account number for display (show first 2 and last 4 digits)
    
    Args:
        account_number: Full account number
    
    Returns:
        Masked account number
    """
    if len(account_number) <= 6:
        return account_number
    
    return f"{account_number[:2]}****{account_number[-4:]}"


def parse_gateway_response(response: str) -> Dict[str, Any]:
    """
    Parse payment gateway response
    
    Args:
        response: JSON response string
    
    Returns:
        Parsed response dictionary
    """
    try:
        return json.loads(response) if response else {}
    except json.JSONDecodeError:
        return {"raw_response": response}


def get_transaction_status_message(status: str) -> str:
    """
    Get user-friendly status message
    
    Args:
        status: Transaction status
    
    Returns:
        User-friendly message
    """
    status_messages = {
        "pending": "Your transaction is being processed",
        "processing": "Your transaction is in progress",
        "completed": "Transaction completed successfully",
        "failed": "Transaction failed. Please try again",
        "cancelled": "Transaction was cancelled"
    }
    return status_messages.get(status, "Transaction status unknown")


def calculate_wallet_stats(transactions: list) -> Dict[str, float]:
    """
    Calculate wallet statistics from transaction list
    
    Args:
        transactions: List of transaction objects
    
    Returns:
        Dictionary with total_earnings and total_withdrawals
    """
    def _value(field):
        return field.value if hasattr(field, 'value') else field

    total_earnings = sum(
        t.amount for t in transactions
        if _value(getattr(t, 'type', None)) == 'credit'
        and _value(getattr(t, 'category', None)) in {'product_sale', 'investment_payout'}
    )

    total_withdrawals = sum(
        t.amount for t in transactions
        if _value(getattr(t, 'type', None)) == 'debit'
        and _value(getattr(t, 'category', None)) == 'withdrawal'
    )

    return {
        "total_earnings": total_earnings,
        "total_withdrawals": total_withdrawals
    }


def is_duplicate_request(idempotency_key: str, existing_requests: list) -> bool:
    """
    Check if a request with the same idempotency key exists
    
    Args:
        idempotency_key: Key to check
        existing_requests: List of existing withdrawal requests
    
    Returns:
        True if duplicate exists
    """
    if not idempotency_key:
        return False
    
    return any(req.idempotency_key == idempotency_key for req in existing_requests)


def sanitize_bank_name(bank_name: str) -> str:
    """
    Sanitize and standardize bank name
    
    Args:
        bank_name: Raw bank name
    
    Returns:
        Sanitized bank name
    """
    # Remove extra spaces and capitalize properly
    return ' '.join(bank_name.strip().split()).title()


def get_bank_code_mapping() -> Dict[str, str]:
    """
    Get mapping of common Nigerian banks and their codes
    
    Returns:
        Dictionary of bank names to codes
    """
    # This would typically come from a config file or database
    return {
        "Access Bank": "044",
        "Citibank": "023",
        "Diamond Bank": "063",
        "Ecobank Nigeria": "050",
        "Fidelity Bank Nigeria": "070",
        "First Bank of Nigeria": "011",
        "First City Monument Bank": "214",
        "Guaranty Trust Bank": "058",
        "Heritage Bank Plc": "030",
        "Jaiz Bank": "301",
        "Keystone Bank Limited": "082",
        "Providus Bank Plc": "101",
        "Polaris Bank": "076",
        "Stanbic IBTC Bank Nigeria Limited": "221",
        "Standard Chartered Bank": "068",
        "Sterling Bank": "232",
        "Suntrust Bank Nigeria Limited": "100",
        "Union Bank of Nigeria": "032",
        "United Bank for Africa": "033",
        "Unity Bank Plc": "215",
        "Wema Bank": "035",
        "Zenith Bank": "057",
        "Opay": "999",
        "Palmpay": "998",
        "Kuda Bank": "090267",
    }
