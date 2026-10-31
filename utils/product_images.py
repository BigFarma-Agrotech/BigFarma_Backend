"""Keep product images out of API responses.

Uploaded images are stored in the products table as base64 data URLs, often
hundreds of KB each. Sending them inside every product list made responses huge
and slow. Responses instead carry a short URL per image, served (and cached by
browsers for a year) by GET /marketplace/products/{public_id}/images/{index}.
Images that are already URLs are passed through unchanged.
"""
import base64
import hashlib
import os
import re
from typing import List, Optional, Tuple

from utils.helpers import split_images

IMAGE_PATH = "/api/v1/marketplace/products/{public_id}/images/{index}"
_DATA_URL = re.compile(r"^data:(image/[\w.+-]+);base64,(.*)$", re.DOTALL)
# Matches our own image URLs (absolute or relative) when they come back in an update
_OWN_URL = re.compile(r"/api/v1/marketplace/products/(?P<public_id>[A-Za-z0-9]+)/images/(?P<index>\d+)")


def _base_url() -> str:
    # Absolute on Render so images load straight from the API (not via the
    # frontend's proxy); relative elsewhere (local dev goes through the Vite proxy)
    return (os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")


def public_images(product) -> List[str]:
    """The product's images as URLs suitable for API responses."""
    images = split_images(product.images) if isinstance(product.images, str) else list(product.images or [])
    result = []
    for index, image in enumerate(images):
        if image.startswith("data:"):
            # The version changes when the image does, so cached copies are never stale
            version = hashlib.sha1(image.encode()).hexdigest()[:10]
            path = IMAGE_PATH.format(public_id=product.public_id, index=index)
            result.append(f"{_base_url()}{path}?v={version}")
        else:
            result.append(image)
    return result


def resolve_image_refs(product, images: List[str]) -> List[str]:
    """Map our own image URLs (sent back when a product is edited) to the stored images."""
    stored = split_images(product.images) if isinstance(product.images, str) else list(product.images or [])
    resolved = []
    for image in images:
        match = _OWN_URL.search(image or "")
        if match and match.group("public_id") == product.public_id and int(match.group("index")) < len(stored):
            resolved.append(stored[int(match.group("index"))])
        else:
            resolved.append(image)
    return resolved


def decode_image(product, index: int) -> Optional[Tuple[bytes, str]]:
    """(bytes, media type) of the product's index-th image if it's stored inline, else None."""
    images = split_images(product.images) if isinstance(product.images, str) else list(product.images or [])
    if index < 0 or index >= len(images):
        return None
    match = _DATA_URL.match(images[index])
    if not match:
        return None
    try:
        return base64.b64decode(match.group(2)), match.group(1)
    except (ValueError, TypeError):
        return None
