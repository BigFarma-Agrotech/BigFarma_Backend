"""Uploaded (base64) images are served by URL instead of inside every product response."""
import base64

from features.marketplace.models import Product
from tests.test_order_notifications_api import env  # noqa: F401

PIXEL = base64.b64encode(b"\x89PNG\r\n\x1a\nfake-png-bytes").decode()
DATA_URL = f"data:image/png;base64,{PIXEL}"


def _db():
    from database import get_db
    import main
    return next(main.app.dependency_overrides[get_db]())


def test_lists_carry_image_urls_and_the_image_endpoint_serves_them(env):
    client, current, farmer_id, _, product_id, _ = env
    db = _db()
    product = db.get(Product, product_id)
    product.images = f"{DATA_URL},https://cdn.example.com/b.jpg"
    product.description = "Fresh green cabbage heads from the farm"
    db.commit()
    public_id = product.public_id

    listed = client.get("/api/v1/marketplace/products").json()["products"][0]
    first, second = listed["images"]
    assert first.startswith(f"/api/v1/marketplace/products/{public_id}/images/0?v=")
    assert second == "https://cdn.example.com/b.jpg"  # URLs pass through
    assert "base64" not in str(listed)

    image = client.get(first)
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert "immutable" in image.headers["cache-control"]
    assert image.content == base64.b64decode(PIXEL)
    # Index 1 is a plain URL, not stored inline
    assert client.get(f"/api/v1/marketplace/products/{public_id}/images/1").status_code == 404

    # Editing sends the URL back; the stored image is kept, not replaced by its URL
    current["user_id"] = farmer_id
    res = client.put(f"/api/v1/marketplace/farmers/products/{public_id}", json={"images": [first]})
    assert res.status_code == 200, res.text
    db.expire_all()
    assert db.get(Product, product_id).images == DATA_URL


def test_large_responses_are_gzipped(env):
    client, current, _, consumer_id, product_id, _ = env
    db = _db()
    product = db.get(Product, product_id)
    product.description = "Fresh green cabbage heads from the farm " * 40
    product.images = "https://cdn.example.com/a.jpg"
    db.commit()
    res = client.get("/api/v1/marketplace/products", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200
    assert res.headers.get("content-encoding") == "gzip"
