"""Product units and minimum order: validation on the product, enforcement at checkout."""
import pytest
from pydantic import ValidationError

from features.marketplace.models import Product
from features.marketplace.schemas import ProductCreate
from tests.test_order_notifications_api import checkout, env, paystack_state  # noqa: F401
from utils.units import normalize_unit, parse_quantity

PRODUCT = dict(name="Yam", category="crop", description="Freshly harvested yam tubers",
               price=500, location="Ibadan", images=["https://example.com/yam.jpg"])


def test_units_parse_and_normalize():
    assert parse_quantity("100 kg") == (100.0, "kg")
    assert parse_quantity("2.5 Liters") == (2.5, "litre")  # decimals kept (was read as 25)
    assert parse_quantity("20 bags") == (20.0, "bag")
    assert parse_quantity("lots") == (None, None)
    assert normalize_unit("Paint Buckets") == "paint bucket"


def test_product_create_rules():
    product = ProductCreate(**PRODUCT, quantity="40 tubers", min_order_quantity=5)
    assert (product.unit, product.min_order_quantity) == ("tuber", 5)

    with pytest.raises(ValidationError, match="whole number"):
        ProductCreate(**PRODUCT, quantity="40 bags", min_order_quantity=2.5)
    with pytest.raises(ValidationError, match="more than the quantity in stock"):
        ProductCreate(**PRODUCT, quantity="4 kg", min_order_quantity=5)
    # Weights can have a fractional minimum
    assert ProductCreate(**PRODUCT, quantity="10 kg", min_order_quantity=0.5).min_order_quantity == 0.5


def _set_product(product_id, **fields):
    from database import get_db
    import main
    db = next(main.app.dependency_overrides[get_db]())
    product = db.get(Product, product_id)
    for key, value in fields.items():
        setattr(product, key, value)
    db.commit()
    return product.public_id


def test_checkout_enforces_minimum_stock_and_whole_units(env):
    client, current, _, consumer_id, product_id, _ = env
    _set_product(product_id, quantity="20 bags", unit="bag", min_order_quantity=3)

    res = checkout(client, current, consumer_id, product_id, quantity=2)
    assert res.status_code == 400 and "minimum order for Cabbage is 3 bag" in res.json()["detail"]
    res = checkout(client, current, consumer_id, product_id, quantity=21)
    assert res.status_code == 400 and "Only 20 bag" in res.json()["detail"]
    res = checkout(client, current, consumer_id, product_id, quantity=3.5)
    assert res.status_code == 400 and "whole bag" in res.json()["detail"]

    res = checkout(client, current, consumer_id, product_id, quantity=3)
    assert res.status_code == 201, res.text
    # The order carries the unit, so the farmer sees "3 bag"
    assert res.json()["orders"][0]["quantity_ordered"] == "3 bag"
    assert res.json()["subtotal"] == 3 * 1200


def test_farmer_updates_minimum_and_restocks(env):
    client, current, farmer_id, _, product_id, _ = env
    public_id = _set_product(product_id, quantity="30 kg", unit="kg", min_order_quantity=1,
                             description=PRODUCT["description"], images=PRODUCT["images"][0])
    current["user_id"] = farmer_id
    url = f"/api/v1/marketplace/farmers/products/{public_id}"

    res = client.put(url, json={"min_order_quantity": 5, "unit": "kg"})
    assert res.status_code == 200, res.text
    assert (res.json()["unit"], res.json()["min_order_quantity"]) == ("kg", 5)

    assert client.put(url, json={"min_order_quantity": 50}).status_code == 400  # more than stock
    # Restocking below the minimum is allowed (buyers just can't order until topped up)
    assert client.put(url, json={"quantity": "3 kg"}).status_code == 200

    # Buyers see the unit and minimum on the marketplace
    listed = client.get("/api/v1/marketplace/products").json()["products"][0]
    assert (listed["unit"], listed["min_order_quantity"]) == ("kg", 5)
