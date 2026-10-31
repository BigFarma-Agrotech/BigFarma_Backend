"""Farmer orders dashboard: per-product order lists, order detail with buyer contact, and status rules."""
from features.marketplace.models import Product, ProductCategory, AvailabilityStatus
from tests.test_order_notifications_api import env, buy  # noqa: F401  (env is a pytest fixture)


def _place_order(client, current, consumer_id, product_id, address=None):
    # Checks out and pays through the fake Paystack; URLs take the random public id
    return buy(client, current, consumer_id, product_id, quantity=2)


DESCRIPTION = "Freshly harvested this week"
IMAGE = "https://example.com/produce.jpg"


def _app_session():
    # The app's own session factory, so rows written here are visible to later requests
    from database import get_db
    import main
    return next(main.app.dependency_overrides[get_db]())


def _add_product(farmer_id, name):
    db = _app_session()
    product = Product(farmer_id=farmer_id, name=name, category=ProductCategory.CROP, description=DESCRIPTION,
                      quantity="10 kg", price=500.0, location="Ibadan", images=IMAGE,
                      availability=AvailabilityStatus.IN_STOCK)
    db.add(product)
    db.commit()
    return product.id


def _make_listable(product_id):
    # The product listing validates description length and images like product creation does
    db = _app_session()
    product = db.get(Product, product_id)
    product.description = DESCRIPTION
    product.images = IMAGE
    db.commit()


def test_orders_filter_by_product_and_products_carry_order_counts(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    _make_listable(product_id)
    other_product_id = _add_product(farmer_id, "Yam")

    first = _place_order(client, current, consumer_id, product_id)
    second = _place_order(client, current, consumer_id, product_id)
    _place_order(client, current, consumer_id, other_product_id)

    current["user_id"] = farmer_id
    product_public_id = _app_session().get(Product, product_id).public_id
    res = client.get("/api/v1/orders/farmer/orders", params={"product_id": product_public_id})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2
    assert {o["public_id"] for o in body["items"]} == {first, second}

    products = client.get("/api/v1/marketplace/farmers/products").json()
    counts = {p["id"]: p["order_count"] for p in products}
    assert counts == {product_id: 2, other_product_id: 1}
    status_counts = {p["id"]: p["order_status_counts"] for p in products}
    assert status_counts == {product_id: {"pending": 2}, other_product_id: {"pending": 1}}

    res = client.put(f"/api/v1/orders/{first}/status", json={"status": "cancelled"})
    assert res.status_code == 200, res.text
    products = client.get("/api/v1/marketplace/farmers/products").json()
    product = next(p for p in products if p["id"] == product_id)
    assert product["order_count"] == 2
    assert product["order_status_counts"] == {"pending": 1, "cancelled": 1}


def test_farmer_order_detail_includes_buyer_contact(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    order_id = _place_order(client, current, consumer_id, product_id)

    current["user_id"] = farmer_id
    res = client.get(f"/api/v1/orders/farmer/orders/{order_id}")
    assert res.status_code == 200, res.text
    order = res.json()
    assert order["public_id"] == order_id
    # Checkout puts the contact on the address and the phone on the order
    assert order["delivery_address"] == "12 Farm Rd, Lekki (Contact: Ada Obi, 08011112222)"
    assert order["customer_phone"] == "08011112222"
    assert "customer_name" in order

    assert client.get("/api/v1/orders/farmer/orders/999999").status_code == 404

    # Buyers use the regular order endpoints, not the farm view
    current["user_id"] = consumer_id
    assert client.get(f"/api/v1/orders/farmer/orders/{order_id}").status_code == 403


def test_farmer_status_changes_follow_the_delivery_flow(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    order_id = _place_order(client, current, consumer_id, product_id)
    current["user_id"] = farmer_id

    def set_status(status):
        return client.put(f"/api/v1/orders/{order_id}/status", json={"status": status})

    # Only the buyer can complete delivery or open a dispute
    assert set_status("delivered").status_code == 409
    assert set_status("delivery_issue").status_code == 409
    # Can't skip shipping
    assert set_status("awaiting_confirmation").status_code == 409

    assert set_status("shipping").status_code == 200
    assert set_status("awaiting_confirmation").status_code == 200
    # No going back once handed to the buyer
    assert set_status("shipping").status_code == 409
    assert set_status("cancelled").status_code == 409

    order = client.get(f"/api/v1/orders/farmer/orders/{order_id}").json()
    assert order["status"] == "awaiting_confirmation"


def test_urls_use_random_public_ids_not_integer_ids(env):
    import re
    client, current, farmer_id, consumer_id, product_id, _ = env
    _make_listable(product_id)
    order_public_id = _place_order(client, current, consumer_id, product_id)
    assert re.fullmatch(r"[A-Za-z0-9]{8}", order_public_id)

    current["user_id"] = farmer_id
    order = client.get(f"/api/v1/orders/farmer/orders/{order_public_id}").json()
    assert re.fullmatch(r"[A-Za-z0-9]{8}", order["product_public_id"])

    # The integer ids no longer work in URLs
    assert client.get(f"/api/v1/orders/farmer/orders/{order['id']}").status_code == 404
    assert client.get(f"/api/v1/marketplace/products/{product_id}").status_code == 404

    reviews = client.get(f"/api/v1/marketplace/products/{order['product_public_id']}/reviews")
    assert reviews.status_code == 200, reviews.text

    products = client.get("/api/v1/marketplace/farmers/products").json()
    assert [p["public_id"] for p in products] == [order["product_public_id"]]
