"""Move product images stored inline (base64) into Supabase Storage.

Each inline image is resized/compressed like new uploads and replaced in the
row by its public URL. Safe to run more than once: rows with only URLs are
skipped. Run from the backend folder:

    python -m scripts.migrate_images_to_storage            # do it
    python -m scripts.migrate_images_to_storage --dry-run  # just report
"""
import sys

import main  # noqa: F401  (registers every model)
from database import SessionLocal
from features.marketplace.models import Product
from services import image_storage
from utils.helpers import split_images


def run(dry_run: bool = False) -> None:
    if not image_storage.is_configured():
        sys.exit("Supabase Storage isn't configured (SUPABASE_S3_* settings).")

    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.images.like("%data:%")).all()
        print(f"{len(products)} product(s) with inline images")
        for product in products:
            images = split_images(product.images)
            before = sum(len(i) for i in images)
            if dry_run:
                print(f"  {product.public_id} {product.name}: {len(images)} image(s), {before // 1024} KB inline")
                continue
            stored = image_storage.store_images(images, f"products/{product.farmer_id}")
            product.images = ",".join(stored)
            db.commit()
            print(f"  {product.public_id} {product.name}: {before // 1024} KB inline -> {stored}")
    finally:
        db.close()


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
