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


@pytest.fixture()
def env(monkeypatch):
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

    # Buyer places an order
    res = client.post("/api/v1/orders/", json={"product_id": product_id, "quantity_ordered": "2",
                                               "delivery_address": "12 Farm Rd (Contact: Ada Obi, 0801)"})
    assert res.status_code == 201, res.text
    order_id = res.json()["public_id"]
    assert res.json()["total_price"] == 2400.0  # 2 x 1200, not the unit price

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


def test_order_rejects_non_numeric_quantity(env):
    client, _, _, _, product_id, _ = env
    res = client.post("/api/v1/orders/", json={"product_id": product_id, "quantity_ordered": "lots",
                                               "delivery_address": "12 Farm Rd"})
    assert res.status_code == 400
