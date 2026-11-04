"""GET /marketplace/products pages 10 at a time and filters on the server."""
from features.marketplace.models import AvailabilityStatus, Product, ProductCategory
from features.users.models import FarmerProfile, FarmType
from tests.test_order_notifications_api import env  # noqa: F401
from tests.test_stock import _db

URL = "/api/v1/marketplace/products"


def _add(db, farmer_id, name, **fields):
    data = dict(farmer_id=farmer_id, name=name, category=ProductCategory.VEGETABLES, description="Fresh",
                quantity="10 kg", unit="kg", price=1000, location="Kano, Nigeria",
                images="https://example.com/x.jpg", is_listed=True)
    data.update(fields)
    db.add(Product(**data))


def _names(res):
    assert res.status_code == 200, res.text
    return {p["name"] for p in res.json()["products"]}


def test_pages_of_ten(env):
    client, _, farmer_id, _, _, _ = env
    db = _db()
    existing = client.get(URL).json()["total_count"]
    for i in range(23 - existing):
        _add(db, farmer_id, f"Item {i}")
    _add(db, farmer_id, "Hidden", is_listed=False)
    db.commit()

    first = client.get(URL).json()
    assert (len(first["products"]), first["page"], first["page_size"]) == (10, 1, 10)
    assert (first["total_count"], first["total_pages"]) == (23, 3)
    assert first["has_next"] and not first["has_previous"]

    last = client.get(URL, params={"page": 3}).json()
    assert len(last["products"]) == 3 and not last["has_next"] and last["has_previous"]

    seen = set()
    for page in (1, 2, 3):
        seen |= {p["public_id"] for p in client.get(URL, params={"page": page}).json()["products"]}
    assert len(seen) == 23  # no product repeated or skipped across pages

    # Old skip/limit callers still work
    legacy = client.get(URL, params={"skip": 0, "limit": 100}).json()
    assert len(legacy["products"]) == 23

    assert client.get(URL, params={"page_size": 101}).status_code == 422
    assert client.get(URL, params={"page": 0}).status_code == 422


def test_server_side_filters(env):
    client, _, farmer_id, _, _, _ = env
    db = _db()
    db.add(FarmerProfile(user_id=farmer_id, full_name="Ada Farmer", home_address="1 Farm Rd", id_document="id.png",
                         farm_name="Green Acres", farm_type=list(FarmType)[0], farm_location="Oyo", farm_size="5 ha"))
    _add(db, farmer_id, "Mango", category=ProductCategory.FRUITS, price=500, location="Lagos")
    _add(db, farmer_id, "Goat", category=ProductCategory.LIVESTOCK, price=50000, location="Kano, Nigeria")
    _add(db, farmer_id, "Old Maize", category=ProductCategory.CROP, price=800, location="Oyo",
         availability=AvailabilityStatus.OUT_OF_STOCK)
    _add(db, farmer_id, "Pricey Tomato", price=10000, discount_percentage=50, location="Kano")
    db.commit()

    assert {"Mango", "Old Maize"} <= _names(client.get(URL, params={"category": "fruits", "page_size": 100}))
    assert "Goat" not in _names(client.get(URL, params={"category": "fruits", "page_size": 100}))
    assert _names(client.get(URL, params={"category": "protein"})) == {"Goat"}
    assert _names(client.get(URL, params={"availability": "out_of_stock"})) == {"Old Maize"}
    assert _names(client.get(URL, params={"location": "lagos"})) == {"Mango"}
    kano = _names(client.get(URL, params={"location": "Kano", "page_size": 100}))
    assert {"Goat", "Pricey Tomato"} <= kano and "Mango" not in kano
    # Max price uses the discounted price (10000 at 50% off = 5000)
    cheap = _names(client.get(URL, params={"max_price": 5000, "page_size": 100}))
    assert "Pricey Tomato" in cheap and "Goat" not in cheap
    assert _names(client.get(URL, params={"q": "mang"})) == {"Mango"}
    assert "Goat" in _names(client.get(URL, params={"q": "green acres", "page_size": 100}))
    assert _names(client.get(URL, params={"category": "minerals"})) == set()

    filtered = client.get(URL, params={"category": "protein"}).json()
    assert (filtered["total_count"], filtered["total_pages"]) == (1, 1)

    locations = client.get(URL + "/locations").json()["locations"]
    assert {"Kano", "Lagos", "Oyo"} <= set(locations)


def test_price_range_filter_and_bounds(env):
    client, _, farmer_id, _, _, _ = env
    db = _db()
    _add(db, farmer_id, "Cheap Pepper", price=300)
    _add(db, farmer_id, "Mid Yam", price=4000)
    _add(db, farmer_id, "Pricey Tomato", price=10000, discount_percentage=50)  # sells at 5000
    _add(db, farmer_id, "Big Goat", category=ProductCategory.LIVESTOCK, price=90000)
    _add(db, farmer_id, "Unlisted Gold", price=999999, is_listed=False)
    db.commit()

    # Both ends inclusive, compared on the discounted price
    middle = _names(client.get(URL, params={"min_price": 4000, "max_price": 5000, "page_size": 100}))
    assert {"Mid Yam", "Pricey Tomato"} <= middle
    assert not {"Cheap Pepper", "Big Goat"} & middle
    assert "Big Goat" in _names(client.get(URL, params={"min_price": 50000, "page_size": 100}))
    assert client.get(URL, params={"min_price": -1}).status_code == 422

    # Slider bounds cover listed products only, after discount
    bounds = client.get(URL + "/price-range").json()
    assert bounds["max_price"] == 90000
    assert bounds["min_price"] <= 300
