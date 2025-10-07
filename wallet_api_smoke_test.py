"""Wallet API smoke test helper.

Usage:
    python wallet_api_smoke_test.py --base-url http://localhost:8000 \
        --email john.farmer@bigfarma.com --password farmer123

The script performs the following sequence:
 1. Authenticate with the provided farmer credentials.
 2. Retrieve wallet balance (auto-creates wallet if needed).
 3. Verify a mock bank account and add it to the wallet.
 4. Fetch the list of bank accounts and set the newest as primary.
 5. Initiate a withdrawal using the active bank account.
 6. Display dashboard and transaction history snapshots.

All responses are printed to stdout. Non-2xx responses raise an exception.
"""

import argparse
import json
import sys
from typing import Any, Dict

import requests

DEFAULT_VERIFY_ACCOUNT = {
    "account_number": "1234567890",
    "bank_code": "058",
}

DEFAULT_SECOND_ACCOUNT = {
    "account_number": "5555666677",
    "bank_code": "057",
}


def request(method: str, url: str, token: str, **kwargs) -> Dict[str, Any]:
    headers = kwargs.pop("headers", {})
    headers.setdefault("Authorization", f"Bearer {token}")
    headers.setdefault("Content-Type", "application/json")
    response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    try:
        payload = response.json()
    except ValueError:
        payload = response.text

    print(f"\n{method} {url}")
    print(f"Status: {response.status_code}")
    print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)

    response.raise_for_status()
    return payload  # type: ignore[return-value]


def login(base_url: str, email: str, password: str) -> str:
    url = f"{base_url}/api/v1/auth/login"
    payload = {"email": email, "password": password}
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token returned")
    print("\nAuthenticated successfully.")
    return token


def ensure_wallet_and_balance(base_url: str, token: str) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/wallet/balance"
    return request("GET", url, token)


def verify_bank_account(base_url: str, token: str, account: Dict[str, str]) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/wallet/bank-accounts/verify"
    return request("POST", url, token, json=account)


def add_bank_account(base_url: str, token: str, account: Dict[str, str]) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/wallet/bank-accounts"
    return request("POST", url, token, json=account)


def list_bank_accounts(base_url: str, token: str) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/wallet/bank-accounts"
    return request("GET", url, token)


def set_primary_account(base_url: str, token: str, account_id: str) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/wallet/bank-accounts/{account_id}/primary"
    return request("PUT", url, token)


def initiate_withdrawal(base_url: str, token: str, amount: float, bank_account_id: str) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/wallet/withdraw"
    payload = {
        "amount": amount,
        "bank_account_id": bank_account_id,
        "idempotency_key": f"smoke-{bank_account_id}",
    }
    return request("POST", url, token, json=payload)


def get_dashboard(base_url: str, token: str) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/wallet/dashboard"
    return request("GET", url, token)


def get_transactions(base_url: str, token: str) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/wallet/transactions"
    return request("GET", url, token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test for wallet API endpoints.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--email", required=True, help="Farmer email")
    parser.add_argument("--password", required=True, help="Farmer password")
    parser.add_argument(
        "--withdraw-amount",
        type=float,
        default=500.0,
        help="Withdrawal amount to test (must be <= ledger balance)",
    )
    args = parser.parse_args()

    try:
        token = login(args.base_url, args.email, args.password)
        ensure_wallet_and_balance(args.base_url, token)

        verify_bank_account(args.base_url, token, DEFAULT_VERIFY_ACCOUNT)
        first_account = add_bank_account(args.base_url, token, DEFAULT_VERIFY_ACCOUNT)
        accounts_resp = list_bank_accounts(args.base_url, token)

        # Optionally add a second account and mark it primary
        verify_bank_account(args.base_url, token, DEFAULT_SECOND_ACCOUNT)
        second_account = add_bank_account(args.base_url, token, DEFAULT_SECOND_ACCOUNT)
        set_primary_account(args.base_url, token, second_account["id"])

        initiate_withdrawal(
            args.base_url,
            token,
            amount=args.withdraw_amount,
            bank_account_id=second_account["id"],
        )

        get_dashboard(args.base_url, token)
        get_transactions(args.base_url, token)

        print("\nWallet smoke test completed successfully.")
    except Exception as exc:  # noqa: BLE001
        print(f"\nWallet smoke test failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
