"""Keeping a product's stock in step with what's been bought.

Stock is stored as text with its unit ("20 bags"). It goes down when an order
is paid (or a group buy share is paid, which reserves it) and comes back when a
paid order is cancelled or an expired group buy is refunded. A product with no
stock left is marked out of stock, and back in stock when some returns.
"""
import logging

from sqlalchemy.orm import Session

from features.marketplace.models import AvailabilityStatus, Product
from utils.units import format_quantity, parse_quantity

logger = logging.getLogger(__name__)


def adjust_stock(db: Session, product_id: int, delta: float) -> Product:
    """Add (delta > 0) or remove (delta < 0) stock. The caller commits.

    The product row is locked so simultaneous payments can't both take the last
    units. Stock never goes below zero; if it would, the shortfall is logged
    (the farmer can cancel what they can't fill)."""
    product = (
        db.query(Product).filter(Product.id == product_id)
        .with_for_update().populate_existing().one()
    )
    stock, stock_unit = parse_quantity(product.quantity)
    if stock is None:
        logger.warning("Product %s stock %r isn't a number; not adjusted", product_id, product.quantity)
        return product

    new_stock = round(stock + delta, 6)
    if new_stock < 0:
        logger.warning("Product %s oversold by %s (stock %s, change %s)", product_id, -new_stock, stock, delta)
        new_stock = 0.0
    product.quantity = format_quantity(new_stock, product.unit or stock_unit)
    product.availability = AvailabilityStatus.OUT_OF_STOCK if new_stock <= 0 else AvailabilityStatus.IN_STOCK
    return product
