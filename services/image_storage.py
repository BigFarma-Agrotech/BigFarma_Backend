"""Product images in Supabase Storage (S3-compatible), resized and compressed.

Uploads arrive as base64 data URLs. Each is resized to at most MAX_DIMENSION px
on its longest side and saved as WebP (quality stepped down only if needed to
stay under TARGET_BYTES), then stored in the bucket. The database keeps just
the public URL, so product lists stay small and images load from Supabase's CDN.
"""
import base64
import io
import logging
import re
import uuid
from functools import lru_cache
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1600          # px, longest side: sharp on phones and desktops
TARGET_BYTES = 300 * 1024     # aim for images of a few hundred KB at most
QUALITIES = (82, 75, 68, 60)  # tried in order until the image fits TARGET_BYTES
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

_DATA_URL = re.compile(r"^data:image/[\w.+-]+;base64,(.*)$", re.DOTALL)


class ImageError(ValueError):
    """The upload isn't a usable image; the message is safe to show."""


def is_configured() -> bool:
    return bool(settings.SUPABASE_S3_ENDPOINT and settings.SUPABASE_S3_ACCESS_KEY_ID
                and settings.SUPABASE_S3_SECRET_ACCESS_KEY)


def public_base_url() -> str:
    """https://<project>.supabase.co/storage/v1/object/public/<bucket>"""
    # The S3 endpoint is https://<project>.storage.supabase.co/storage/v1/s3
    project = re.match(r"https://([^.]+)\.", settings.SUPABASE_S3_ENDPOINT or "")
    host = f"https://{project.group(1)}.supabase.co" if project else (settings.SUPABASE_URL or "").rstrip("/")
    return f"{host}/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}"


@lru_cache(maxsize=1)
def _client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.SUPABASE_S3_ENDPOINT,
        aws_access_key_id=settings.SUPABASE_S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.SUPABASE_S3_SECRET_ACCESS_KEY,
        region_name=settings.SUPABASE_S3_REGION,
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )


def compress_image(raw: bytes) -> bytes:
    """Resize to MAX_DIMENSION and encode as WebP, keeping quality as high as the size allows."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImageError("Each image must be smaller than 15 MB.")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise ImageError("One of the images couldn't be read. Please upload a JPG, PNG or WebP photo.")

    image = ImageOps.exif_transpose(image)  # phone photos come in sideways otherwise
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    encoded = b""
    for quality in QUALITIES:
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=quality, method=6)
        encoded = buffer.getvalue()
        if len(encoded) <= TARGET_BYTES:
            break
    return encoded


def upload_image(data_url: str, folder: str) -> str:
    """Compress a base64 data URL image, store it, and return its public URL."""
    match = _DATA_URL.match(data_url or "")
    if not match:
        raise ImageError("Invalid image upload.")
    try:
        raw = base64.b64decode(match.group(1))
    except (ValueError, TypeError):
        raise ImageError("Invalid image upload.")

    webp = compress_image(raw)
    key = f"{folder}/{uuid.uuid4().hex}.webp"
    _client().put_object(
        Bucket=settings.SUPABASE_STORAGE_BUCKET,
        Key=key,
        Body=webp,
        ContentType="image/webp",
        CacheControl="public, max-age=31536000, immutable",
    )
    logger.info("Stored image %s (%s KB from %s KB)", key, len(webp) // 1024, len(raw) // 1024)
    return f"{public_base_url()}/{key}"


def store_images(images: list, folder: str) -> list:
    """Upload any data-URL images in the list; URLs are kept as they are.

    Without storage configured, images are returned unchanged (kept inline)."""
    if not is_configured():
        return images
    return [upload_image(image, folder) if (image or "").startswith("data:") else image for image in images]


def key_for_url(url: str) -> Optional[str]:
    """The bucket key for one of our public image URLs (None for any other URL)."""
    prefix = f"{public_base_url()}/"
    return url[len(prefix):] if url and url.startswith(prefix) else None


def delete_images(urls: list) -> None:
    """Best-effort removal of images we stored (e.g. replaced or deleted product photos)."""
    if not is_configured():
        return
    keys = [k for k in (key_for_url(u) for u in urls) if k]
    if not keys:
        return
    try:
        _client().delete_objects(
            Bucket=settings.SUPABASE_STORAGE_BUCKET,
            Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
        )
    except Exception as exc:  # never fail a product update over clean-up
        logger.warning("Couldn't delete old images %s: %s", keys, exc)
