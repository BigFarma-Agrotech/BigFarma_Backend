"""Checkout through Paystack (faked in the env fixture): totals, paid-only visibility, verify and webhook."""
import hashlib
import hmac
import json

from features.marketplace.models import AvailabilityStatus, Order, Product
from tests.test_order_notifications_api import CALLBACK, checkout, env, paystack_state  # noqa: F401


def _db():
    from database import get_db
    import main
    return next(main.app.dependency_overrides[get_db]())


def test_checkout_charges_server_totals_and_hides_orders_until_paid(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    res = checkout(client, current, consumer_id, product_id, quantity=2)
    assert res.status_code == 201, res.text
    body = res.json()
    # 2 x 1200, door delivery 1500, 7.5% tax on the items
    assert (body["subtotal"], body["delivery_fee"], body["tax"], body["amount"]) == (2400, 1500, 180, 4080)
    assert body["status"] == "pending"
    assert body["authorization_url"].startswith("https://checkout.paystack.com/")
    assert paystack_state["transactions"][body["reference"]] == 408000  # kobo

    # Not paid yet: nobody sees the order and the farmer hasn't been told
    assert client.get("/api/v1/orders").json() == []
    current["user_id"] = farmer_id
    assert client.get("/api/v1/orders/farmer/orders").json()["items"] == []
    assert client.get("/api/v1/notifications").json() == []

    # Buyer returns from Paystack; verifying marks it paid
    current["user_id"] = consumer_id
    paid = client.get(f"/api/v1/payments/verify/{body['reference']}").json()
    assert paid["status"] == "success" and paid["paid_at"]
    order_id = paid["orders"][0]["public_id"]
    assert [o["public_id"] for o in client.get("/api/v1/orders").json()] == [order_id]
    current["user_id"] = farmer_id
    assert [o["public_id"] for o in client.get("/api/v1/orders/farmer/orders").json()["items"]] == [order_id]
    assert [n["notification_type"] for n in client.get("/api/v1/notifications").json()] == ["new_order"]

    # Verifying again changes nothing and doesn't notify twice
    current["user_id"] = consumer_id
    assert client.get(f"/api/v1/payments/verify/{body['reference']}").json()["status"] == "success"
    current["user_id"] = farmer_id
    assert len(client.get("/api/v1/notifications").json()) == 1


def test_pickup_has_no_delivery_fee(env):
    client, current, _, consumer_id, product_id, _ = env
    body = checkout(client, current, consumer_id, product_id, quantity=1, delivery_option="pickup").json()
    assert (body["delivery_fee"], body["amount"]) == (0, 1290)


def test_abandoned_and_mismatched_payments_never_mark_orders_paid(env):
    client, current, _, consumer_id, product_id, _ = env
    reference = checkout(client, current, consumer_id, product_id).json()["reference"]
    paystack_state["status"] = "abandoned"
    assert client.get(f"/api/v1/payments/verify/{reference}").json()["status"] == "abandoned"
    assert client.get("/api/v1/orders").json() == []

    # Paystack says success but for less than the total
    paystack_state.update(status="success", amount_offset=-100)
    reference = checkout(client, current, consumer_id, product_id).json()["reference"]
    result = client.get(f"/api/v1/payments/verify/{reference}").json()
    assert result["status"] == "failed"
    assert client.get("/api/v1/orders").json() == []


def test_webhook_needs_a_valid_signature_and_marks_paid(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    reference = checkout(client, current, consumer_id, product_id).json()["reference"]
    payload = json.dumps({"event": "charge.success", "data": {
        "reference": reference, "status": "success", "amount": 408000, "currency": "NGN"}}).encode()

    bad = client.post("/api/v1/payments/paystack/webhook", content=payload,
                      headers={"x-paystack-signature": "nope", "content-type": "application/json"})
    assert bad.status_code == 401

    signature = hmac.new(b"sk_test_fake", payload, hashlib.sha512).hexdigest()
    ok = client.post("/api/v1/payments/paystack/webhook", content=payload,
                     headers={"x-paystack-signature": signature, "content-type": "application/json"})
    assert ok.status_code == 200
    current["user_id"] = farmer_id
    assert len(client.get("/api/v1/orders/farmer/orders").json()["items"]) == 1


def test_checkout_errors(env, monkeypatch):
    client, current, farmer_id, consumer_id, product_id, _ = env

    # Only our own sites as the return address
    current["user_id"] = consumer_id
    res = client.post("/api/v1/payments/checkout", json={
        "items": [{"product_id": product_id, "quantity": 1}], "delivery_address": "12 Farm Rd",
        "contact_name": "Ada", "contact_phone": "0801", "callback_url": "https://evil.example/steal"})
    assert res.status_code == 400

    # Out-of-stock items are named and nothing is created
    db = _db()
    db.get(Product, product_id).availability = AvailabilityStatus.OUT_OF_STOCK
    db.commit()
    res = checkout(client, current, consumer_id, product_id)
    assert res.status_code == 400 and "Cabbage" in res.json()["detail"]
    assert _db().query(Order).count() == 0
    db.get(Product, product_id).availability = AvailabilityStatus.IN_STOCK
    db.commit()

    # Farmers can't check out; someone else's payment isn't visible
    assert checkout(client, current, farmer_id, product_id).status_code == 403
    reference = checkout(client, current, consumer_id, product_id).json()["reference"]
    current["user_id"] = farmer_id
    assert client.get(f"/api/v1/payments/verify/{reference}").status_code == 404

    # Without a Paystack key, checkout says so instead of failing later
    from config import settings
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", None)
    assert checkout(client, current, consumer_id, product_id).status_code == 503

    # The old pay-later endpoints are gone
    assert client.post("/api/v1/orders", json={}).status_code == 410
    assert client.post("/api/v1/marketplace/orders", json={}).status_code == 410
