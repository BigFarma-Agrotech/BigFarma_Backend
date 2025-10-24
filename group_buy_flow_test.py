"""Quick integration test for group-buy endpoints."""
import argparse
import random
import string
import sys
from typing import Dict

import requests

def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def login(base_url: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but access_token missing")
    return token

def create_product(base_url: str, token: str) -> int:
    suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    payload = {
        "name": f"GroupBuy Test Yams {suffix}",
        "category": "crop",
        "description": "Bulk yams purchase for cooperative testing.",
        "quantity": "200 units",
        "price": 1500.0,
        "discount_percentage": 0,
        "location": "Ibadan",
        "images": ["https://example.com/yams.jpg"],
    }
    resp = requests.post(
        f"{base_url}/api/v1/marketplace/farmers/products",
        json=payload,
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]

def create_group(base_url: str, token: str, product_id: int) -> Dict:
    payload = {
        "group_name": "Test Cooperative Purchase",
        "group_description": "Automated test for group buying workflow.",
        "group_location": "Ibadan",
        "product_id": product_id,
        "target_quantity": "200 units",
        "target_quantity_numeric": 200,
        "quantity_unit": "units",
        "individual_contribution": 1000.0,
        "is_public": True,
        "max_members": 10,
    }
    resp = requests.post(
        f"{base_url}/api/v1/groups",
        json=payload,
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def join_group(base_url: str, token: str, group_id: int) -> Dict:
    payload = {
        "group_id": group_id,
        "quantity_committed": 10,
        "contribution_amount": 1000.0,
    }
    resp = requests.post(
        f"{base_url}/api/v1/groups/{group_id}/join",
        json=payload,
        headers=auth_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def main() -> None:
    parser = argparse.ArgumentParser(description="Group buy API smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--farmer-email", default="john.farmer@bigfarma.com")
    parser.add_argument("--farmer-password", default="farmer123")
    parser.add_argument("--creator-email", default="jane.consumer@bigfarma.com")
    parser.add_argument("--creator-password", default="consumer123")
    parser.add_argument("--joiner-email", default="ahmed.buyer@bigfarma.com")
    parser.add_argument("--joiner-password", default="consumer123")
    args = parser.parse_args()

    try:
        print("Logging in users…")
        farmer_token = login(args.base_url, args.farmer_email, args.farmer_password)
        creator_token = login(args.base_url, args.creator_email, args.creator_password)
        joiner_token = login(args.base_url, args.joiner_email, args.joiner_password)

        print("Creating product for group buy…")
        product_id = create_product(args.base_url, farmer_token)
        print("Product ID:", product_id)

        print("Creating group buy…")
        group = create_group(args.base_url, creator_token, product_id)
        group_id = group["id"]
        print("Group created:", group_id)

        print("Joining group as second member…")
        member = join_group(args.base_url, joiner_token, group_id)
        print("Joined group member status:", member["status"])

        print("Fetching group details…")
        resp = requests.get(
            f"{args.base_url}/api/v1/groups/{group_id}",
            headers=auth_headers(creator_token),
            timeout=30,
        )
        resp.raise_for_status()
        detail = resp.json()
        print("Current member count:", len(detail.get("members", [])))

        print("Group buy flow completed successfully.")
    except requests.HTTPError as err:
        print("Request failed:", err.response.status_code)
        print(err.response.text)
        sys.exit(1)
    except Exception as exc:
        print("Error:", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
