"""Product images go to Supabase Storage resized and compressed (S3 client faked)."""
import base64
import io

import pytest
from PIL import Image

from config import settings
from services import image_storage


def _photo_data_url(width=4000, height=3000):
    # A photo-like image (smooth shading plus grain), saved the way phones do: a big JPEG
    shading = Image.radial_gradient("L").resize((width, height))
    grain = Image.effect_noise((width, height), 24)
    image = Image.merge("RGB", (shading, Image.blend(shading, grain, 0.3), grain))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode(), len(buffer.getvalue())


class FakeS3:
    def __init__(self):
        self.objects, self.deleted = {}, []

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl):
        self.objects[Key] = (Bucket, Body, ContentType, CacheControl)

    def delete_objects(self, Bucket, Delete):
        self.deleted += [o["Key"] for o in Delete["Objects"]]


@pytest.fixture()
def fake_s3(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_S3_ENDPOINT", "https://abcproject.storage.supabase.co/storage/v1/s3")
    monkeypatch.setattr(settings, "SUPABASE_S3_ACCESS_KEY_ID", "key")
    monkeypatch.setattr(settings, "SUPABASE_S3_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_BUCKET", "product-images")
    client = FakeS3()
    monkeypatch.setattr(image_storage, "_client", lambda: client)
    return client


def test_upload_resizes_to_webp_and_returns_public_url(fake_s3):
    data_url, original_size = _photo_data_url()
    url = image_storage.upload_image(data_url, "products/7")

    assert url.startswith("https://abcproject.supabase.co/storage/v1/object/public/product-images/products/7/")
    assert url.endswith(".webp")
    (bucket, body, content_type, cache), = fake_s3.objects.values()
    assert (bucket, content_type) == ("product-images", "image/webp")
    assert "immutable" in cache

    stored = Image.open(io.BytesIO(body))
    assert max(stored.size) == image_storage.MAX_DIMENSION      # 4000x3000 -> 1600x1200
    assert stored.size == (1600, 1200)                          # aspect ratio kept
    assert len(body) < original_size / 10                       # far smaller than the upload


def test_store_images_keeps_urls_and_deletes_only_our_images(fake_s3):
    data_url, _ = _photo_data_url(800, 600)
    stored = image_storage.store_images([data_url, "https://cdn.example.com/x.jpg"], "products/1")
    assert stored[1] == "https://cdn.example.com/x.jpg"
    assert stored[0].startswith(image_storage.public_base_url())

    image_storage.delete_images(stored)
    assert fake_s3.deleted == [image_storage.key_for_url(stored[0])]


def test_bad_uploads_are_rejected_clearly(fake_s3):
    with pytest.raises(image_storage.ImageError):
        image_storage.upload_image("data:image/png;base64," + base64.b64encode(b"not an image").decode(), "x")
    with pytest.raises(image_storage.ImageError):
        image_storage.upload_image("https://example.com/a.jpg", "x")


def test_without_storage_images_stay_inline(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_S3_ENDPOINT", None)
    assert image_storage.store_images(["data:image/png;base64,AAAA"], "x") == ["data:image/png;base64,AAAA"]
