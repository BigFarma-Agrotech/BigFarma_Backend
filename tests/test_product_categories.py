"""Farmers can list products under the finer categories (roots and tubers, legumes, oils, ...)."""
import base64
import io

from PIL import Image

from features.users.models import FarmerProfile, FarmType
from tests.test_order_notifications_api import env  # noqa: F401
from tests.test_stock import _db


def _photo():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 150, 60)).save(buffer, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def test_create_product_in_new_categories(env):
    client, current, farmer_id, _, _, _ = env
    db = _db()
    db.add(FarmerProfile(user_id=farmer_id, full_name="Ada Farmer", home_address="1 Farm Rd", id_document="id.png",
                         farm_name="Green Acres", farm_type=list(FarmType)[0], farm_location="Oyo", farm_size="5 ha"))
    db.commit()
    current["user_id"] = farmer_id

    for name, category in [("Yam", "roots_tubers"), ("Beans", "legumes"), ("Palm Oil", "oils")]:
        res = client.post("/api/v1/marketplace/farmers/products", json={
            "name": name, "category": category, "description": "Fresh from our farm in Oyo state.",
            "quantity": "40 kg", "unit": "kg", "min_order_quantity": 2, "price": 1500,
            "location": "Oyo", "images": [_photo()]})
        assert res.status_code == 200, res.text
        assert res.json()["category"] == category

    res = client.post("/api/v1/marketplace/farmers/products", json={
        "name": "Rocks", "category": "minerals", "description": "Not something we sell here.",
        "quantity": "1 kg", "price": 10, "location": "Oyo", "images": [_photo()]})
    assert res.status_code == 422
