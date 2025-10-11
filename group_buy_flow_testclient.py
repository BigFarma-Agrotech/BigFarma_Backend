"""Group buy flow test using FastAPI TestClient."""
from fastapi.testclient import TestClient
from main import app
import random
import string

client = TestClient(app, raise_server_exceptions=False)


def login(email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"login": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json().get("access_token")
    assert token, "access_token missing"
    return token


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def create_product(token: str) -> int:
    suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    payload = {
        "name": f"GroupBuy Test Cassava {suffix}",
        "category": "crop",
        "description": "Casual bulk cassava purchase for testing flow.",
        "quantity": "100 units",
        "price": 1200.0,
        "discount_percentage": 0,
        "location": "Abeokuta",
        "images": ["https://example.com/cassava.jpg"],
    }
    resp = client.post(
        "/api/v1/marketplace/farmers/products",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def create_group(token: str, product_id: int) -> int:
    payload = {
        "group_name": "QA Cooperative",
        "group_description": "Testing group buy integration.",
        "group_location": "Abeokuta",
        "product_id": product_id,
        "target_quantity": "100 units",
        "target_quantity_numeric": 100,
        "quantity_unit": "units",
        "individual_contribution": 800.0,
        "is_public": True,
        "max_members": 5,
    }
    resp = client.post("/api/v1/groups", json=payload, headers=auth_headers(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def join_group(token: str, group_id: int):
    payload = {
        "group_id": group_id,
        "quantity_committed": 10,
        "contribution_amount": 800.0,
    }
    resp = client.post(
        f"/api/v1/groups/{group_id}/join",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def run_flow():
    farmer_token = login("john.farmer@bigfarma.com", "farmer123")
    creator_token = login("jane.consumer@bigfarma.com", "consumer123")
    joiner_token = login("ahmed.buyer@bigfarma.com", "consumer123")

    product_id = create_product(farmer_token)
    group_id = create_group(creator_token, product_id)
    member = join_group(joiner_token, group_id)
    print("Group ID:", group_id)
    print("Join status:", member["status"])

    detail = client.get(
        f"/api/v1/groups/{group_id}",
        headers=auth_headers(creator_token),
    )
    if detail.status_code != 200:
        print("Group detail failed", detail.status_code, detail.text)
        return
    data = detail.json()
    print("Members:", len(data.get("members", [])))


if __name__ == "__main__":
    run_flow()
