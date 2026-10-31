"""Group buy end to end: members pay their share via Paystack (faked); a full group places one bulk order."""
from features.auth.models import User, UserCategory
from features.group_buy.models import GroupBuy, GroupStatus
from features.marketplace.models import Order, Product
from tests.test_order_notifications_api import CALLBACK, env, paystack_state  # noqa: F401


def _db():
    from database import get_db
    import main
    return next(main.app.dependency_overrides[get_db]())


def _second_buyer():
    db = _db()
    user = User(email="buyer2@example.com", password="x", category=UserCategory.CONSUMER, is_verified=True, is_active=True)
    db.add(user)
    db.commit()
    return user.id


def _pay(client, current, user_id, group_id, quantity, status="success"):
    current["user_id"] = user_id
    res = client.post(f"/api/v1/groups/{group_id}/checkout", json={
        "quantity": quantity, "contact_name": "Ada Obi", "contact_phone": "08011112222", "callback_url": CALLBACK})
    if res.status_code != 201:
        return res
    paystack_state["status"] = status
    paid = client.get(f"/api/v1/payments/verify/{res.json()['reference']}")
    paystack_state["status"] = "success"
    return paid


def test_group_buy_paid_shares_complete_into_one_bulk_order(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    db = _db()
    product = db.get(Product, product_id)
    product.unit, product.quantity, product.min_order_quantity = "kg", "30 kg", 5
    db.commit()
    buyer2 = _second_buyer()

    # Target below the farmer's minimum order is refused; 10 kg is fine
    current["user_id"] = consumer_id
    body = {"group_name": "Lekki Cabbage Group", "group_location": "Lekki Phase 1", "product_id": product_id,
            "target_quantity": "3 kg", "target_quantity_numeric": 3}
    assert client.post("/api/v1/groups", json=body).status_code == 400
    res = client.post("/api/v1/groups", json={**body, "target_quantity": "10 kg", "target_quantity_numeric": 10})
    assert res.status_code == 201, res.text
    group_id = res.json()["public_id"]
    assert res.json()["individual_contribution"] == 1200  # price per kg

    # The creator hasn't paid yet, so nobody's a member, but it's in "my groups"
    details = client.get(f"/api/v1/groups/{group_id}").json()
    assert (details["members_count"], details["remaining_quantity"], details["unit_price"]) == (0, 10, 1200)
    assert [g["public_id"] for g in client.get("/api/v1/groups").json()] == [group_id]

    # Creator pays for 4 kg: 4 x 1200 + 7.5% tax
    paid = _pay(client, current, consumer_id, group_id, 4)
    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert (body["status"], body["purpose"], body["group_public_id"]) == ("success", "group_buy", group_id)
    assert body["amount"] == 4800 + 360
    details = client.get(f"/api/v1/groups/{group_id}").json()
    assert (details["is_member"], details["progress_percentage"], details["group_wallet_balance"]) == (True, 40, 4800)

    # Buyer 2 can't take more than is left, abandons once (slot freed), then pays for the rest
    assert _pay(client, current, buyer2, group_id, 7).status_code == 400
    abandoned = _pay(client, current, buyer2, group_id, 6, status="abandoned")
    assert abandoned.json()["status"] == "abandoned"
    current["user_id"] = buyer2
    assert client.get(f"/api/v1/groups/{group_id}").json()["is_member"] is False
    current["user_id"] = farmer_id
    assert client.get("/api/v1/orders/farmer/orders").json()["items"] == []  # nothing until the group fills

    assert _pay(client, current, buyer2, group_id, 6).json()["status"] == "success"

    # Full: the group completes and the farmer gets one paid bulk order for 10 kg
    group = _db().query(GroupBuy).filter(GroupBuy.public_id == group_id).one()
    assert (group.status, group.current_quantity, group.group_wallet_balance) == (GroupStatus.COMPLETED, 10, 12000)
    current["user_id"] = farmer_id
    orders = client.get("/api/v1/orders/farmer/orders").json()["items"]
    assert len(orders) == 1
    assert (orders[0]["quantity_ordered"], orders[0]["total_price"]) == ("10 kg", 12000)
    assert "Lekki Phase 1" in orders[0]["delivery_address"]
    assert _db().query(Order).filter(Order.group_id == group.id).count() == 1

    # Members are told, and the notification links to the group
    current["user_id"] = buyer2
    notes = client.get("/api/v1/notifications").json()
    reached = [n for n in notes if n["title"] == "Group target reached!"]
    assert reached and reached[0]["reference_public_id"] == group_id

    # A completed group takes no more members; paying without Paystack is gone
    assert _pay(client, current, buyer2, group_id, 1).status_code == 400
    assert client.post(f"/api/v1/groups/{group_id}/join", json={}).status_code == 410
    assert client.post(f"/api/v1/groups/{group_id}/contribute", json={}).status_code == 410


def test_deadline_shown_enforced_and_overdue_groups_refunded(env, monkeypatch):
    import asyncio
    from datetime import datetime, timedelta, timezone
    from features.group_buy.payments import GroupPaymentService
    from features.marketplace.models import Payment
    from features.payments import paystack

    client, current, _, consumer_id, product_id, _ = env
    db = _db()
    product = db.get(Product, product_id)
    product.unit, product.quantity = "kg", "30 kg"
    db.commit()

    current["user_id"] = consumer_id
    body = {"group_name": "Deadline Group", "group_location": "Yaba, Lagos", "product_id": product_id,
            "target_quantity": "10 kg", "target_quantity_numeric": 10, "max_members": 4}
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    assert client.post("/api/v1/groups", json={**body, "deadline": past}).status_code == 400
    res = client.post("/api/v1/groups", json={**body, "deadline": future})
    assert res.status_code == 201, res.text
    group_id = res.json()["public_id"]

    details = client.get(f"/api/v1/groups/{group_id}").json()
    assert details["deadline"] and details["max_members"] == 4

    # A member pays 3 kg, then the deadline passes with the group unfilled
    assert _pay(client, current, consumer_id, group_id, 3).json()["status"] == "success"
    group = db.query(GroupBuy).filter(GroupBuy.public_id == group_id).one()
    group.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    refunded = []
    async def fake_refund(reference):
        refunded.append(reference)
        return {"status": "pending"}
    monkeypatch.setattr(paystack, "refund_transaction", fake_refund)

    assert asyncio.run(GroupPaymentService(_db()).expire_overdue_groups()) == 1
    check = _db()
    group = check.query(GroupBuy).filter(GroupBuy.public_id == group_id).one()
    assert group.status == GroupStatus.CANCELLED and group.group_wallet_balance == 0
    payment = check.query(Payment).filter(Payment.purpose == "group_buy").one()
    assert refunded == [payment.reference] and payment.status == "refunded"

    titles = [n["title"] for n in client.get("/api/v1/notifications").json()]
    assert "Group closed: refund on the way" in titles
    # A closed group takes no payments, and isn't expired twice
    assert _pay(client, current, consumer_id, group_id, 1).status_code == 400
    assert asyncio.run(GroupPaymentService(_db()).expire_overdue_groups()) == 0


def test_last_slot_must_take_the_rest_so_the_group_closes(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    db = _db()
    product = db.get(Product, product_id)
    product.unit, product.quantity = "kg", "30 kg"
    db.commit()
    buyer2 = _second_buyer()

    current["user_id"] = consumer_id
    res = client.post("/api/v1/groups", json={
        "group_name": "Two Member Group", "group_location": "Yaba, Lagos", "product_id": product_id,
        "target_quantity": "10 kg", "target_quantity_numeric": 10, "max_members": 2})
    group_id = res.json()["public_id"]
    assert _pay(client, current, consumer_id, group_id, 4).json()["status"] == "success"

    # Buyer 2 has the last slot: less than the 6 kg left is refused
    res = _pay(client, current, buyer2, group_id, 2)
    assert res.status_code == 400 and "last slot" in res.json()["detail"] and "6 kg" in res.json()["detail"]
    assert _pay(client, current, buyer2, group_id, 6).json()["status"] == "success"

    # Full on both counts: closed, and the farmer has the bulk order
    group = _db().query(GroupBuy).filter(GroupBuy.public_id == group_id).one()
    assert group.status == GroupStatus.COMPLETED
    current["user_id"] = farmer_id
    assert [o["quantity_ordered"] for o in client.get("/api/v1/orders/farmer/orders").json()["items"]] == ["10 kg"]


def test_minimum_share_and_top_ups(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    db = _db()
    product = db.get(Product, product_id)
    product.unit, product.quantity = "kg", "30 kg"
    db.commit()
    buyer2 = _second_buyer()

    current["user_id"] = consumer_id
    body = {"group_name": "Min Share Group", "group_location": "Yaba, Lagos", "product_id": product_id,
            "target_quantity": "10 kg", "target_quantity_numeric": 10}
    assert client.post("/api/v1/groups", json={**body, "min_member_quantity": 11}).status_code == 400
    res = client.post("/api/v1/groups", json={**body, "min_member_quantity": 3})
    group_id = res.json()["public_id"]
    assert res.json()["min_member_quantity"] == 3

    # Joining below the minimum share is refused
    res = _pay(client, current, consumer_id, group_id, 2)
    assert res.status_code == 400 and "at least 3 kg" in res.json()["detail"]
    assert _pay(client, current, consumer_id, group_id, 3).json()["status"] == "success"

    # Topping up: no minimum, no contact needed, share grows only once paid
    current["user_id"] = consumer_id
    res = client.post(f"/api/v1/groups/{group_id}/checkout", json={"quantity": 2, "callback_url": CALLBACK})
    assert res.status_code == 201, res.text
    paystack_state["status"] = "abandoned"
    client.get(f"/api/v1/payments/verify/{res.json()['reference']}")
    paystack_state["status"] = "success"
    details = client.get(f"/api/v1/groups/{group_id}").json()
    assert details["is_member"] and details["current_quantity"] == 3  # abandoned top-up changed nothing

    res = client.post(f"/api/v1/groups/{group_id}/checkout", json={"quantity": 5, "callback_url": CALLBACK})
    client.get(f"/api/v1/payments/verify/{res.json()['reference']}")
    details = client.get(f"/api/v1/groups/{group_id}").json()
    assert (details["current_quantity"], details["members_count"], details["group_wallet_balance"]) == (8, 1, 9600)
    assert [m["quantity_committed"] for m in details["members"]] == [8]

    # Only 2 kg left, less than the 3 kg minimum: a new member may take just the rest
    assert details["join_minimum"] == 2
    assert _pay(client, current, buyer2, group_id, 2).json()["status"] == "success"
    current["user_id"] = farmer_id
    assert [o["quantity_ordered"] for o in client.get("/api/v1/orders/farmer/orders").json()["items"]] == ["10 kg"]
