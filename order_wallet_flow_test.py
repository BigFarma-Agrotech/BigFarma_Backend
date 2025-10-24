"""End-to-end wallet credit flow test using HTTP requests."""
import argparse
import random
import string
import sys
from typing import Dict

import requests


def login(base_url: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but access_token missing")
    return token


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_product(base_url: str, token: str) -> int:
    suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    payload = {
        "name": f"Wallet Test Tomatoes {suffix}",
        "category": "crop",
        "description": "Fresh organic tomatoes grown without chemicals.",
        "quantity": "50 crates",
        "price": 2000.0,
        "discount_percentage": 0,
        "location": "Ikeja, Lagos",
        "images": ["https://example.com/tomatoes.jpg"],
    }
    resp = requests.post(
        f"{base_url}/api/v1/marketplace/farmers/products",
        json=payload,
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_order(base_url: str, token: str, product_id: int) -> Dict:
    payload = {
        "product_id": product_id,
        "quantity_ordered": "5",
        "delivery_address": "123 Sample Street, Lagos",
    }
    resp = requests.post(
        f"{base_url}/api/v1/orders",
        json=payload,
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def update_order_status(base_url: str, token: str, order_id: int, status: str) -> None:
    payload = {"status": status}
    resp = requests.put(
        f"{base_url}/api/v1/orders/{order_id}/status",
        json=payload,
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()


def confirm_delivery(base_url: str, token: str, order_id: int) -> Dict:
    resp = requests.post(
        f"{base_url}/api/v1/orders/{order_id}/confirm-delivery",
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_wallet_balance(base_url: str, token: str) -> Dict:
    resp = requests.get(
        f"{base_url}/api/v1/api/wallet/balance",
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_wallet_transactions(base_url: str, token: str) -> Dict:
    resp = requests.get(
        f"{base_url}/api/v1/api/wallet/transactions",
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wallet credit integration test")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--farmer-email", default="john.farmer@bigfarma.com")
    parser.add_argument("--farmer-password", default="farmer123")
    parser.add_argument("--consumer-email", default="jane.consumer@bigfarma.com")
    parser.add_argument("--consumer-password", default="consumer123")
    args = parser.parse_args()

    try:
        farmer_token = login(args.base_url, args.farmer_email, args.farmer_password)
        consumer_token = login(args.base_url, args.consumer_email, args.consumer_password)

        print("Creating product...")
        product_id = create_product(args.base_url, farmer_token)
        print(f"Product ID: {product_id}")

        print("Creating order...")
        order = create_order(args.base_url, consumer_token, product_id)
        order_id = order["id"]
        print(f"Order created with ID: {order_id}")

        print("Updating order status to awaiting_confirmation...")
        update_order_status(args.base_url, farmer_token, order_id, "awaiting_confirmation")

        print("Confirming delivery (should credit wallet)...")
        confirm_delivery(args.base_url, consumer_token, order_id)

        balance = get_wallet_balance(args.base_url, farmer_token)
        print("Wallet balance:", balance)

        transactions = get_wallet_transactions(args.base_url, farmer_token)
        print("Recent transactions:")
        for tx in transactions.get("transactions", []):
            print(f" - {tx['reference']} | {tx['category']} | {tx['amount']} | {tx['description']}")

        print("\nFlow completed successfully.")
    except requests.HTTPError as err:
        print("Request failed:", err.response.status_code, err.response.text)
        sys.exit(1)
    except Exception as exc:
        print("Error:", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
