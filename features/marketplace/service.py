import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, false

from utils.units import is_count_unit, parse_quantity
from utils.product_images import resolve_image_refs
from utils.helpers import split_images
from services import image_storage
from features.marketplace.models import Product, Order, Review, AvailabilityStatus, OrderStatus, ProductCategory, OrderPaymentStatus
from features.marketplace.schemas import ProductCreate, ProductUpdate, OrderCreate, ReviewCreate
from features.users.models import FarmerProfile

logger = logging.getLogger(__name__)

ANIMAL_CATEGORIES = {ProductCategory.LIVESTOCK, ProductCategory.POULTRY, ProductCategory.FISH, ProductCategory.DAIRY_EGGS}
CATEGORY_VALUES = {c.value for c in ProductCategory}
AVAILABILITY_VALUES = {a.value for a in AvailabilityStatus}

class MarketplaceService:
    def __init__(self, db: Session):
        self.db = db

    # Product methods
    def create_product(self, farmer_id: int, product_data: ProductCreate) -> Product:
        # Get farmer profile to get farm name
        farmer_profile = self.db.query(FarmerProfile).filter(FarmerProfile.user_id == farmer_id).first()
        if not farmer_profile:
            raise ValueError("Farmer profile not found")
        
        # Check for duplicate product
        existing_product = self.db.query(Product).filter(
            Product.farmer_id == farmer_id,
            Product.name.ilike(product_data.name),
            Product.is_listed == True
        ).first()
        
        if existing_product:
            raise ValueError(f"Product '{product_data.name}' already exists. Please edit the existing listing.")
        
        # Validate product data
        if not product_data.description or len(product_data.description) < 20:
            raise ValueError("Product description must be at least 20 characters long")
        
        if not product_data.images or len(product_data.images) == 0:
            raise ValueError("At least one product image is required")
        
        if product_data.price <= 0:
            raise ValueError("Product price must be greater than 0")
        
        # Uploads are resized and stored in Supabase Storage; the row keeps the URLs
        images_str = ",".join(self._store_images(product_data.images, farmer_id))
        
        # Out of stock when the quantity is zero (e.g. "0 kg")
        stock, _ = parse_quantity(product_data.quantity)
        availability = AvailabilityStatus.OUT_OF_STOCK if stock is not None and stock <= 0 else AvailabilityStatus.IN_STOCK
        
        product = Product(
            farmer_id=farmer_id,
            name=product_data.name,
            category=product_data.category,
            description=product_data.description,
            quantity=product_data.quantity,
            unit=product_data.unit,
            min_order_quantity=product_data.min_order_quantity,
            price=product_data.price,
            discount_percentage=product_data.discount_percentage or 0.0,
            location=product_data.location,
            images=images_str,
            availability=availability,
            is_approved=True,  # Auto-approve for now
            is_listed=True,
            total_ratings=0,
            average_rating=0.0
        )
        
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update_product(self, product_id: int, farmer_id: int, update_data: ProductUpdate) -> Optional[Product]:
        product = self.db.query(Product).filter(Product.id == product_id, Product.farmer_id == farmer_id).first()
        if not product:
            return None
        
        update_dict = update_data.dict(exclude_unset=True)
        
        # Handle images conversion. Kept images come back as the URLs we sent
        # out; new ones arrive as data URLs and are resized and stored.
        removed_images = set()
        if 'images' in update_dict and update_dict['images']:
            if isinstance(update_dict['images'], list):
                kept = resolve_image_refs(product, update_dict['images'])
                new_images = self._store_images(kept, farmer_id)
                removed_images = set(split_images(product.images)) - set(new_images)
                update_dict['images'] = ",".join(new_images)
        
        # Update availability if quantity changes
        if 'quantity' in update_dict and update_dict['quantity']:
            stock, stock_unit = parse_quantity(update_dict['quantity'])
            update_dict['availability'] = (
                AvailabilityStatus.OUT_OF_STOCK if stock is not None and stock <= 0 else AvailabilityStatus.IN_STOCK
            )
            if not update_dict.get('unit'):
                update_dict['unit'] = stock_unit or product.unit

        # When the farmer sets the minimum order (or the unit), it has to fit the
        # product as it will be after the update. Restocking alone is never blocked.
        if 'min_order_quantity' in update_dict or 'unit' in update_data.model_fields_set:
            min_order = update_dict.get('min_order_quantity') or product.min_order_quantity or 1
            unit = update_dict.get('unit') or product.unit
            stock, _ = parse_quantity(update_dict.get('quantity') or product.quantity)
            if is_count_unit(unit) and not float(min_order).is_integer():
                raise ValueError(f"Minimum order must be a whole number of {unit}")
            if stock is not None and stock > 0 and min_order > stock:
                raise ValueError("Minimum order can't be more than the quantity in stock")
        
        for key, value in update_dict.items():
            setattr(product, key, value)
        
        self.db.commit()
        self.db.refresh(product)
        # Photos the farmer took off the product no longer need storing
        image_storage.delete_images(list(removed_images))
        return product

    @staticmethod
    def _store_images(images: list, farmer_id: int) -> list:
        try:
            return image_storage.store_images(images, f"products/{farmer_id}")
        except image_storage.ImageError:
            raise
        except Exception as exc:
            logger.error("Image upload failed: %s", exc)
            raise ValueError("We couldn't upload your images right now. Please try again.")

    def get_farmer_products(self, farmer_id: int) -> List[Product]:
        return self.db.query(Product).filter(Product.farmer_id == farmer_id).order_by(Product.created_at.desc()).all()

    def get_product(self, product_id: int) -> Optional[Product]:
        return self.db.query(Product).filter(Product.id == product_id).first()

    def get_all_products(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Product]:
        """Get ALL products from the database without any filters"""
        query = self.db.query(Product).order_by(Product.created_at.desc()).filter(
            # Product.is_approved == True, 
            Product.is_listed == True
        )
        
        return query.offset(skip).limit(limit).all()
    
    def list_marketplace_products(
        self,
        page: int = 1,
        page_size: int = 10,
        q: Optional[str] = None,
        categories: Optional[List[str]] = None,
        availability: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        max_price: Optional[float] = None,
    ) -> tuple[List[Product], int]:
        """One page of listed products matching the marketplace filters, plus the total match count."""
        query = self.db.query(Product).filter(Product.is_listed == True)  # noqa: E712

        term = (q or "").strip().lower()
        if term:
            like = f"%{term}%"
            # Category is an enum, so match its values in Python ("roots tubers" finds roots_tubers)
            matching_categories = [c for c in ProductCategory if term in c.value.replace("_", " ") or term in c.value]
            farm_matches = self.db.query(FarmerProfile.user_id).filter(
                or_(func.lower(FarmerProfile.full_name).like(like), func.lower(FarmerProfile.farm_name).like(like))
            )
            query = query.filter(or_(
                func.lower(Product.name).like(like),
                func.lower(Product.description).like(like),
                func.lower(Product.location).like(like),
                Product.category.in_(matching_categories) if matching_categories else false(),
                Product.farmer_id.in_(farm_matches),
            ))

        if categories:
            wanted = set()
            for raw in categories:
                key = raw.strip().lower()
                if key == "protein":  # the marketplace's "Protein" tile
                    wanted.update(ANIMAL_CATEGORIES)
                elif key in CATEGORY_VALUES:
                    wanted.add(ProductCategory(key))
            # Older products were all listed as "crop", so a crop tile still finds them
            if any(c not in ANIMAL_CATEGORIES for c in wanted):
                wanted.add(ProductCategory.CROP)
            query = query.filter(Product.category.in_(wanted)) if wanted else query.filter(false())

        if availability:
            statuses = [AvailabilityStatus(a) for a in availability if a in AVAILABILITY_VALUES]
            query = query.filter(Product.availability.in_(statuses)) if statuses else query.filter(false())

        if locations:
            # "Kano" matches "Kano" and "Kano, Nigeria"
            clauses = []
            for raw in locations:
                loc = raw.strip().lower()
                if loc:
                    clauses += [func.lower(Product.location) == loc, func.lower(Product.location).like(f"{loc},%")]
            if clauses:
                query = query.filter(or_(*clauses))

        if max_price is not None:
            effective_price = Product.price * (1 - func.coalesce(Product.discount_percentage, 0) / 100.0)
            query = query.filter(effective_price <= max_price)

        total = query.order_by(None).count()
        products = (
            query.order_by(Product.created_at.desc(), Product.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return products, total

    def get_marketplace_locations(self) -> List[str]:
        """Distinct towns of listed products ("Kano, Nigeria" -> "Kano"), for the location filter."""
        rows = self.db.query(Product.location).filter(Product.is_listed == True).distinct().all()  # noqa: E712
        towns = {}
        for (location,) in rows:
            town = str(location or "").split(",")[0].strip()
            if town:
                towns.setdefault(town.lower(), town)
        return sorted(towns.values(), key=str.lower)

    def get_products_count(self) -> int:
        """Get total count of ALL products in the database"""
        return self.db.query(func.count(Product.id)).scalar() or 0

    def delete_product(self, product_id: int, farmer_id: int) -> bool:
        product = self.db.query(Product).filter(Product.id == product_id, Product.farmer_id == farmer_id).first()
        if product:
            images = split_images(product.images)
            self.db.delete(product)
            self.db.commit()
            image_storage.delete_images(images)
            return True
        return False

    def add_discount(self, product_id: int, farmer_id: int, discount_percentage: float) -> Optional[Product]:
        product = self.db.query(Product).filter(Product.id == product_id, Product.farmer_id == farmer_id).first()
        if product:
            product.discount_percentage = discount_percentage
            self.db.commit()
            self.db.refresh(product)
            return product
        return None

    def remove_discount(self, product_id: int, farmer_id: int) -> Optional[Product]:
        return self.add_discount(product_id, farmer_id, 0.0)

    # Search and filtering methods
    def search_products(self, query: str, skip: int = 0, limit: int = 100) -> List[Product]:
        """Search products by name, description, or farm name"""
        if not query:
            return self.get_all_products(skip, limit)
        
        search_term = f"%{query}%"
        
        products = self.db.query(Product).join(FarmerProfile, Product.farmer_id == FarmerProfile.user_id).filter(
            or_(
                Product.name.ilike(search_term),
                Product.description.ilike(search_term),
                FarmerProfile.farm_name.ilike(search_term),
                FarmerProfile.farm_type.ilike(search_term)
            )
        ).offset(skip).limit(limit).all()
        
        return products

    def filter_products(self, filters: Dict[str, Any], skip: int = 0, limit: int = 100) -> List[Product]:
        """Filter products by various criteria"""
        query = self.db.query(Product)
        
        # Apply filters
        if filters.get('categories'):
            query = query.filter(Product.category.in_(filters['categories']))
        
        if filters.get('min_price') is not None:
            query = query.filter(Product.price >= filters['min_price'])
        
        if filters.get('max_price') is not None:
            query = query.filter(Product.price <= filters['max_price'])
        
        if filters.get('locations'):
            location_filters = [Product.location.ilike(f"%{loc}%") for loc in filters['locations']]
            query = query.filter(or_(*location_filters))
        
        products = query.offset(skip).limit(limit).all()
        return products

    def get_similar_products(self, product_id: int, limit: int = 6) -> List[Product]:
        """Get products similar to the given product"""
        current_product = self.get_product(product_id)
        if not current_product:
            return []
        
        # Find similar products by same category
        similar_products = self.db.query(Product).filter(
            and_(
                Product.id != product_id,
                Product.category == current_product.category
            )
        ).limit(limit).all()
        
        return similar_products

    def get_products_by_crop_type(self, crop_type: str, skip: int = 0, limit: int = 100) -> List[Product]:
        """Get products filtered by specific crop type"""
        return self.db.query(Product).filter(
            or_(
                Product.name.ilike(f"%{crop_type}%"),
                Product.description.ilike(f"%{crop_type}%"),
                Product.category.ilike(f"%{crop_type}%")
            )
        ).offset(skip).limit(limit).all()

    # Order methods
    def create_order(self, consumer_id: int, order_data: OrderCreate) -> Optional[Order]:
        product = self.get_product(order_data.product_id)
        if not product:
            return None
        
        # Calculate total price with discount
        discounted_price = product.price * (1 - product.discount_percentage / 100)
        total_price = discounted_price
        
        # Generate order number
        from datetime import datetime
        import random
        import string
        date_part = datetime.now().strftime("%Y%m%d")
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        order_number = f"BF{date_part}{random_part}"
        
        order = Order(
            product_id=order_data.product_id,
            consumer_id=consumer_id,
            quantity_ordered=order_data.quantity_ordered,
            total_price=total_price,
            delivery_address=order_data.delivery_address,
            order_number=order_number
        )
        
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def get_user_orders(self, user_id: int) -> List[Order]:
        return self.db.query(Order).filter(
            Order.consumer_id == user_id, Order.payment_status == OrderPaymentStatus.PAID
        ).order_by(Order.created_at.desc()).all()

    def update_order_status(self, order_id: int, status: OrderStatus) -> Optional[Order]:
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if order:
            order.status = status
            self.db.commit()
            self.db.refresh(order)
            return order
        return None

    # Review methods
    def create_review(self, consumer_id: int, review_data: ReviewCreate) -> Optional[Review]:
        product = self.get_product(review_data.product_id)
        if not product:
            return None
        
        # Check if user already reviewed this product
        existing_review = self.db.query(Review).filter(
            Review.product_id == review_data.product_id,
            Review.consumer_id == consumer_id
        ).first()
        
        if existing_review:
            raise ValueError("You have already reviewed this product")
        
        review = Review(
            product_id=review_data.product_id,
            consumer_id=consumer_id,
            rating=review_data.rating,
            comment=review_data.comment
        )
        
        # Update product ratings
        current_total = product.total_ratings or 0
        current_avg = product.average_rating or 0.0
        
        new_total = current_total + 1
        new_avg = ((current_avg * current_total) + review_data.rating) / new_total
        
        product.total_ratings = new_total
        product.average_rating = new_avg
        
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def get_product_reviews(self, product_id: int) -> List[Review]:
        return self.db.query(Review).filter(Review.product_id == product_id).order_by(Review.created_at.desc()).all()

    def get_total_product_count(self) -> int:
        """Get total count of ALL products in the database"""
        return self.db.query(func.count(Product.id)).scalar() or 0