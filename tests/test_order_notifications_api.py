"""End-to-end: a buyer orders, the farmer sees it and is notified, status updates notify the buyer."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from core.dependencies import get_current_active_user
from database import Base, get_db
from features.auth.models import User, UserCategory
from features.marketplace.models import Product, ProductCategory, AvailabilityStatus
from services.email_service import email_service


paystack_state = {"transactions": {}, "status": "success", "amount_offset": 0}

CALLBACK = "http://localhost:5173/payment-processing"


def checkout(client, current, consumer_id, product_id, quantity=2, delivery_option="door-delivery"):
    current["user_id"] = consumer_id
    return client.post("/api/v1/payments/checkout", json={
        "items": [{"product_id": product_id, "quantity": quantity}],
        "delivery_address": "12 Farm Rd, Lekki", "contact_name": "Ada Obi", "contact_phone": "08011112222",
        "delivery_option": delivery_option, "callback_url": CALLBACK,
    })


def buy(client, current, consumer_id, product_id, quantity=2):
    """Check out and pay (fake Paystack); returns the paid order's public id."""
    res = checkout(client, current, consumer_id, product_id, quantity)
    assert res.status_code == 201, res.text
    paid = client.get(f"/api/v1/payments/verify/{res.json()['reference']}")
    assert paid.status_code == 200 and paid.json()["status"] == "success", paid.text
    return paid.json()["orders"][0]["public_id"]


@pytest.fixture()
def env(monkeypatch):
    paystack_state.update(transactions={}, status="success", amount_offset=0)
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    farmer = User(email="farmer@example.com", password="x", category=UserCategory.FARMER, is_verified=True, is_active=True)
    consumer = User(email="consumer@example.com", password="x", category=UserCategory.CONSUMER, is_verified=True, is_active=True)
    db.add_all([farmer, consumer])
    db.commit()
    product = Product(farmer_id=farmer.id, name="Cabbage", category=ProductCategory.CROP, description="Fresh",
                      quantity="30 kg", price=1200.0, location="Ibadan", images="",
                      availability=AvailabilityStatus.IN_STOCK)
    db.add(product)
    db.commit()

    # Record emails instead of calling Brevo
    sent = []
    async def fake_send(to_email, subject, html_content):
        sent.append((to_email, subject))
        return True
    monkeypatch.setattr(email_service, "send_email", fake_send)

    # Stand in for Paystack: record initialized transactions; verify reports them
    # with the status set in paystack_state (success by default) and the right amount
    from config import settings
    from features.payments import paystack
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_fake")
    # Never upload to the real Supabase bucket from tests
    monkeypatch.setattr(settings, "SUPABASE_S3_ENDPOINT", None)
    async def fake_initialize(email, amount_kobo, reference, callback_url, metadata):
        paystack_state["transactions"][reference] = amount_kobo
        return {"authorization_url": f"https://checkout.paystack.com/{reference}", "reference": reference}
    async def fake_verify(reference):
        return {"status": paystack_state["status"], "currency": "NGN",
                "amount": paystack_state["transactions"][reference] + paystack_state["amount_offset"],
                "gateway_response": "Approved"}
    monkeypatch.setattr(paystack, "initialize_transaction", fake_initialize)
    monkeypatch.setattr(paystack, "verify_transaction", fake_verify)

    current = {"user_id": consumer.id}

    def override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    # Keep each request's session alive (as the real dependency does) so
    # lazy-loaded relationships like the user's profile still work
    user_sessions = []

    def override_user():
        s = Session()
        user_sessions.append(s)
        return s.get(User, current["user_id"])

    main.app.dependency_overrides[get_db] = override_db
    main.app.dependency_overrides[get_current_active_user] = override_user
    client = TestClient(main.app)
    yield client, current, farmer.id, consumer.id, product.id, sent
    main.app.dependency_overrides.clear()
    for s in user_sessions:
        s.close()
    db.close()
    Base.metadata.drop_all(engine)


def test_order_flow_notifies_both_sides(env):
    client, current, farmer_id, consumer_id, product_id, sent = env

    # Buyer checks out and pays
    order_id = buy(client, current, consumer_id, product_id, quantity=2)
    current["user_id"] = consumer_id
    assert client.get("/api/v1/orders").json()[0]["total_price"] == 2400.0  # 2 x 1200, not the unit price

    # Farmer sees it on the farm orders endpoint and has a notification
    current["user_id"] = farmer_id
    farm = client.get("/api/v1/orders/farmer/orders").json()
    assert [o["public_id"] for o in farm["items"]] == [order_id]
    farmer_notes = client.get("/api/v1/notifications/").json()
    assert [n["notification_type"] for n in farmer_notes] == ["new_order"]
    # Carries the order's public ids so the app can link straight to it
    assert farmer_notes[0]["reference_public_id"] == order_id
    assert farmer_notes[0]["product_public_id"] == farm["items"][0]["product_public_id"]
    # Times carry their UTC offset so clients don't read them as local time
    assert farmer_notes[0]["created_at"].endswith("+00:00")
    assert client.get("/api/v1/notifications/unread-count").json() == {"unread_count": 1}

    # Marking it read returns the same links
    read = client.patch(f"/api/v1/notifications/{farmer_notes[0]['id']}/read").json()
    assert read["is_read"] and read["reference_public_id"] == order_id

    # Both emails went out: confirmation to buyer, new-order alert to farmer
    recipients = {to for to, _ in sent}
    assert {"consumer@example.com", "farmer@example.com"} <= recipients

    # Farmer ships it; buyer gets a status notification
    res = client.put(f"/api/v1/orders/{order_id}/status", json={"status": "shipping"})
    assert res.status_code == 200, res.text
    current["user_id"] = consumer_id
    titles = [n["title"] for n in client.get("/api/v1/notifications/").json()]
    assert "Order on its way" in titles

    # Farmer marks it delivered, buyer confirms; farmer is told the wallet was credited
    current["user_id"] = farmer_id
    client.put(f"/api/v1/orders/{order_id}/status", json={"status": "awaiting_confirmation"})
    current["user_id"] = consumer_id
    assert client.post(f"/api/v1/orders/{order_id}/confirm-delivery").status_code == 200
    current["user_id"] = farmer_id
    types = [n["notification_type"] for n in client.get("/api/v1/notifications/").json()]
    assert types[0] == "delivery_confirmed"


def test_checkout_rejects_bad_quantity(env):
    client, current, _, consumer_id, product_id, _ = env
    assert checkout(client, current, consumer_id, product_id, quantity=0).status_code == 422
    assert checkout(client, current, consumer_id, product_id, quantity="lots").status_code == 422


def test_list_routes_answer_without_trailing_slash(env):
    # The frontend calls these without the slash so Vercel's rewrite can proxy them
    client, current, farmer_id, consumer_id, product_id, _ = env
    buy(client, current, consumer_id, product_id, quantity=1)
    for path in ["/api/v1/orders", "/api/v1/orders/", "/api/v1/notifications", "/api/v1/notifications/"]:
        res = client.get(path, follow_redirects=False)
        assert res.status_code == 200, (path, res.status_code)
        assert isinstance(res.json(), list)


def test_delete_clear_and_expiry(env):
    from datetime import datetime, timedelta, timezone
    from features.notifications.models import Notification
    import main
    from database import get_db

    client, current, farmer_id, consumer_id, product_id, _ = env
    for _ in range(3):
        buy(client, current, consumer_id, product_id, quantity=1)
    current["user_id"] = farmer_id
    notes = client.get("/api/v1/notifications").json()
    assert len(notes) == 3

    # Delete one; another user's id can't be deleted
    assert client.delete(f"/api/v1/notifications/{notes[0]['id']}").status_code == 204
    assert client.delete(f"/api/v1/notifications/{notes[0]['id']}").status_code == 404
    assert len(client.get("/api/v1/notifications").json()) == 2
    assert client.get("/api/v1/notifications/unread-count").json() == {"unread_count": 2}

    # One past the retention period disappears from the list and the count
    db = next(main.app.dependency_overrides[get_db]())
    old = db.get(Notification, notes[1]["id"])
    old.created_at = datetime.now(timezone.utc) - timedelta(days=31)
    db.commit()
    assert [n["id"] for n in client.get("/api/v1/notifications").json()] == [notes[2]["id"]]
    assert db.get(Notification, notes[1]["id"]) is None  # actually deleted

    # Clear all
    res = client.delete("/api/v1/notifications")
    assert res.status_code == 200 and res.json()["deleted"] == 1
    assert client.get("/api/v1/notifications").json() == []
    assert client.get("/api/v1/notifications/unread-count").json() == {"unread_count": 0}
