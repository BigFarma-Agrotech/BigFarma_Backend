"""Stock follows sales: paid orders and group shares take it, cancellations and refunds give it back."""
import asyncio
from datetime import datetime, timedelta, timezone

from features.group_buy.models import GroupBuy
from features.marketplace.models import AvailabilityStatus, Product
from tests.test_order_notifications_api import CALLBACK, checkout, env, paystack_state  # noqa: F401


def _db():
    from database import get_db
    import main
    return next(main.app.dependency_overrides[get_db]())


def _stock(product_id):
    product = _db().get(Product, product_id)
    return product.quantity, product.availability


def _set(product_id, quantity, unit="bag"):
    db = _db()
    product = db.get(Product, product_id)
    product.quantity, product.unit, product.min_order_quantity = quantity, unit, 1
    product.availability = AvailabilityStatus.IN_STOCK
    db.commit()


def test_paid_orders_reduce_stock_and_cancelling_restores_it(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    _set(product_id, "10 bags")

    # Abandoned payment: stock untouched
    paystack_state["status"] = "abandoned"
    ref = checkout(client, current, consumer_id, product_id, quantity=3).json()["reference"]
    client.get(f"/api/v1/payments/verify/{ref}")
    paystack_state["status"] = "success"
    assert _stock(product_id)[0] == "10 bags"

    # Paid: 10 - 3
    ref = checkout(client, current, consumer_id, product_id, quantity=3).json()["reference"]
    order_id = client.get(f"/api/v1/payments/verify/{ref}").json()["orders"][0]["public_id"]
    assert _stock(product_id)[0] == "7 bags"

    # Can't order more than is left
    res = checkout(client, current, consumer_id, product_id, quantity=8)
    assert res.status_code == 400 and "Only 7 bags" in res.json()["detail"]

    # The farmer cancels: the 3 bags are back
    current["user_id"] = farmer_id
    assert client.put(f"/api/v1/orders/{order_id}/status", json={"status": "cancelled"}).status_code == 200
    assert _stock(product_id)[0] == "10 bags"


def test_selling_the_last_units_marks_out_of_stock(env):
    client, current, _, consumer_id, product_id, _ = env
    _set(product_id, "2 bags")
    ref = checkout(client, current, consumer_id, product_id, quantity=2).json()["reference"]
    client.get(f"/api/v1/payments/verify/{ref}")
    assert _stock(product_id) == ("0 bags", AvailabilityStatus.OUT_OF_STOCK)
    # Nothing left to buy
    assert checkout(client, current, consumer_id, product_id, quantity=1).status_code == 400


def test_group_shares_reserve_stock_and_expiry_returns_it(env, monkeypatch):
    from features.group_buy.payments import GroupPaymentService
    from features.payments import paystack

    client, current, _, consumer_id, product_id, _ = env
    _set(product_id, "30 kg", unit="kg")
    current["user_id"] = consumer_id
    group_id = client.post("/api/v1/groups", json={
        "group_name": "Stock Group", "group_location": "Yaba, Lagos", "product_id": product_id,
        "target_quantity": "20 kg", "target_quantity_numeric": 20}).json()["public_id"]

    ref = client.post(f"/api/v1/groups/{group_id}/checkout", json={
        "quantity": 5, "contact_name": "Ada", "contact_phone": "08011112222",
        "delivery_address": "3 Herbert Macaulay Way, Yaba", "callback_url": CALLBACK}).json()["reference"]
    client.get(f"/api/v1/payments/verify/{ref}")
    assert _stock(product_id)[0] == "25 kg"  # 5 kg reserved for the group

    # Stock sold elsewhere: a share bigger than what's left is refused
    _set(product_id, "4 kg", unit="kg")
    res = client.post(f"/api/v1/groups/{group_id}/checkout", json={"quantity": 6, "callback_url": CALLBACK})
    assert res.status_code == 400 and "only has 4 kg" in res.json()["detail"]

    # The group expires unfilled: the reserved 5 kg comes back
    db = _db()
    group = db.query(GroupBuy).filter(GroupBuy.public_id == group_id).one()
    group.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    async def fake_refund(reference):
        return {}
    monkeypatch.setattr(paystack, "refund_transaction", fake_refund)
    asyncio.run(GroupPaymentService(_db()).expire_overdue_groups())
    assert _stock(product_id)[0] == "9 kg"
