"""
Configuration settings for wallet feature
"""
from pydantic import BaseSettings
from typing import Optional


class WalletConfig(BaseSettings):
    """Wallet configuration settings"""
    
    # Withdrawal limits
    MINIMUM_WITHDRAWAL_AMOUNT: float = 500.0
    MAXIMUM_WITHDRAWAL_AMOUNT: Optional[float] = None  # No maximum by default
    WITHDRAWAL_FEE_PERCENTAGE: float = 1.5
    MAXIMUM_WITHDRAWAL_FEE: float = 1000.0
    
    # Transaction settings
    TRANSACTION_REFERENCE_PREFIX: str = "BF"  # BigFarma prefix
    
    # Bank account settings
    MAX_BANK_ACCOUNTS_PER_USER: int = 5
    BANK_ACCOUNT_VERIFICATION_TIMEOUT: int = 30  # seconds
    
    # Currency settings
    DEFAULT_CURRENCY: str = "NGN"
    SUPPORTED_CURRENCIES: list = ["NGN"]
    
    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Payment gateway settings (would be environment-specific)
    PAYMENT_GATEWAY_PROVIDER: str = "paystack"  # or "flutterwave", "stripe", etc.
    PAYMENT_GATEWAY_API_KEY: Optional[str] = None
    PAYMENT_GATEWAY_SECRET_KEY: Optional[str] = None
    PAYMENT_GATEWAY_WEBHOOK_SECRET: Optional[str] = None
    
    # Feature flags
    ENABLE_INSTANT_WITHDRAWALS: bool = False
    ENABLE_WITHDRAWAL_SCHEDULING: bool = False
    ENABLE_MULTI_CURRENCY: bool = False
    
    # Notification settings
    SEND_WITHDRAWAL_SMS: bool = True
    SEND_WITHDRAWAL_EMAIL: bool = True
    SEND_TRANSACTION_ALERTS: bool = True
    
    # Security settings
    REQUIRE_2FA_FOR_WITHDRAWALS: bool = False
    WITHDRAWAL_RATE_LIMIT: int = 5  # Max withdrawals per day
    
    class Config:
        env_prefix = "WALLET_"
        case_sensitive = True


# Global config instance
wallet_config = WalletConfig()


# Bank configuration (Nigerian banks)
NIGERIAN_BANKS = {
    "044": {
        "name": "Access Bank",
        "code": "044",
        "active": True
    },
    "023": {
        "name": "Citibank",
        "code": "023",
        "active": True
    },
    "063": {
        "name": "Diamond Bank",
        "code": "063",
        "active": False  # Now merged with Access Bank
    },
    "050": {
        "name": "Ecobank Nigeria",
        "code": "050",
        "active": True
    },
    "070": {
        "name": "Fidelity Bank Nigeria",
        "code": "070",
        "active": True
    },
    "011": {
        "name": "First Bank of Nigeria",
        "code": "011",
        "active": True
    },
    "214": {
        "name": "First City Monument Bank",
        "code": "214",
        "active": True
    },
    "058": {
        "name": "Guaranty Trust Bank",
        "code": "058",
        "active": True
    },
    "030": {
        "name": "Heritage Bank Plc",
        "code": "030",
        "active": True
    },
    "301": {
        "name": "Jaiz Bank",
        "code": "301",
        "active": True
    },
    "082": {
        "name": "Keystone Bank Limited",
        "code": "082",
        "active": True
    },
    "101": {
        "name": "Providus Bank Plc",
        "code": "101",
        "active": True
    },
    "076": {
        "name": "Polaris Bank",
        "code": "076",
        "active": True
    },
    "221": {
        "name": "Stanbic IBTC Bank Nigeria Limited",
        "code": "221",
        "active": True
    },
    "068": {
        "name": "Standard Chartered Bank",
        "code": "068",
        "active": True
    },
    "232": {
        "name": "Sterling Bank",
        "code": "232",
        "active": True
    },
    "100": {
        "name": "Suntrust Bank Nigeria Limited",
        "code": "100",
        "active": True
    },
    "032": {
        "name": "Union Bank of Nigeria",
        "code": "032",
        "active": True
    },
    "033": {
        "name": "United Bank for Africa",
        "code": "033",
        "active": True
    },
    "215": {
        "name": "Unity Bank Plc",
        "code": "215",
        "active": True
    },
    "035": {
        "name": "Wema Bank",
        "code": "035",
        "active": True
    },
    "057": {
        "name": "Zenith Bank",
        "code": "057",
        "active": True
    },
    "090267": {
        "name": "Kuda Bank",
        "code": "090267",
        "active": True
    },
    "999": {
        "name": "Opay",
        "code": "999",
        "active": True
    },
    "998": {
        "name": "PalmPay",
        "code": "998",
        "active": True
    }
}


def get_active_banks():
    """Get list of active banks"""
    return {
        code: bank for code, bank in NIGERIAN_BANKS.items() 
        if bank["active"]
    }


def get_bank_name(bank_code: str) -> Optional[str]:
    """Get bank name by code"""
    bank = NIGERIAN_BANKS.get(bank_code)
    return bank["name"] if bank else None


def is_valid_bank_code(bank_code: str) -> bool:
    """Check if bank code is valid and active"""
    bank = NIGERIAN_BANKS.get(bank_code)
    return bank is not None and bank["active"]
