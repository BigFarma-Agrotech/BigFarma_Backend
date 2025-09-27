import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from features.marketplace.models import Product, Order, Review, AvailabilityStatus, OrderStatus, ProductCategory
from features.marketplace.schemas import ProductCreate, ProductUpdate, OrderCreate, ReviewCreate
from features.users.models import FarmerProfile

logger = logging.getLogger(__name__)

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
        
        # Convert images list to comma-separated string
        images_str = ",".join(product_data.images)
        
        # Set default availability based on quantity
        availability = AvailabilityStatus.IN_STOCK
        if product_data.quantity:
            try:
                # Extract numeric value from quantity string (e.g., "10 kg" -> 10)
                quantity_value = int(''.join(filter(str.isdigit, product_data.quantity.split()[0])))
                if quantity_value <= 0:
                    availability = AvailabilityStatus.OUT_OF_STOCK
            except (ValueError, IndexError):
                availability = AvailabilityStatus.IN_STOCK
        
        product = Product(
            farmer_id=farmer_id,
            name=product_data.name,
            category=product_data.category,
            description=product_data.description,
            quantity=product_data.quantity,
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
        
        # Handle images conversion
        if 'images' in update_dict and update_dict['images']:
            if isinstance(update_dict['images'], list):
                update_dict['images'] = ",".join(update_dict['images'])
        
        # Update availability if quantity changes
        if 'quantity' in update_dict and update_dict['quantity']:
            try:
                quantity_value = int(''.join(filter(str.isdigit, update_dict['quantity'].split()[0])))
                update_dict['availability'] = AvailabilityStatus.IN_STOCK if quantity_value > 0 else AvailabilityStatus.OUT_OF_STOCK
            except (ValueError, IndexError):
                update_dict['availability'] = AvailabilityStatus.IN_STOCK
        
        for key, value in update_dict.items():
            setattr(product, key, value)
        
        self.db.commit()
        self.db.refresh(product)
        return product

    def get_farmer_products(self, farmer_id: int) -> List[Product]:
        return self.db.query(Product).filter(Product.farmer_id == farmer_id).order_by(Product.created_at.desc()).all()

    def get_product(self, product_id: int) -> Optional[Product]:
        return self.db.query(Product).filter(Product.id == product_id).first()

    def get_all_products(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Product]:
        """Get all products without any filters"""
        query = self.db.query(Product).filter(
            Product.is_approved == True, 
            Product.is_listed == True
        ).order_by(Product.created_at.desc())
        
        return query.offset(skip).limit(limit).all()
    
    def get_products_count(self) -> int:
        """Get total count of all approved and listed products"""
        return self.db.query(func.count(Product.id)).filter(
            Product.is_approved == True,
            Product.is_listed == True
        ).scalar() or 0

    def delete_product(self, product_id: int, farmer_id: int) -> bool:
        product = self.db.query(Product).filter(Product.id == product_id, Product.farmer_id == farmer_id).first()
        if product:
            self.db.delete(product)
            self.db.commit()
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
            and_(
                Product.is_approved == True,
                Product.is_listed == True,
                Product.availability == AvailabilityStatus.IN_STOCK,
                or_(
                    Product.name.ilike(search_term),
                    Product.description.ilike(search_term),
                    FarmerProfile.farm_name.ilike(search_term),
                    FarmerProfile.farm_type.ilike(search_term)
                )
            )
        ).offset(skip).limit(limit).all()
        
        return products

    def filter_products(self, filters: Dict[str, Any], skip: int = 0, limit: int = 100) -> List[Product]:
        """Filter products by various criteria"""
        query = self.db.query(Product).filter(
            Product.is_approved == True,
            Product.is_listed == True,
            Product.availability == AvailabilityStatus.IN_STOCK
        )
        
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
                Product.is_approved == True,
                Product.is_listed == True,
                Product.availability == AvailabilityStatus.IN_STOCK,
                Product.id != product_id,
                Product.category == current_product.category
            )
        ).limit(limit).all()
        
        return similar_products

    def get_products_by_crop_type(self, crop_type: str, skip: int = 0, limit: int = 100) -> List[Product]:
        """Get products filtered by specific crop type"""
        return self.db.query(Product).filter(
            Product.is_approved == True,
            Product.is_listed == True,
            Product.availability == AvailabilityStatus.IN_STOCK,
            or_(
                Product.name.ilike(f"%{crop_type}%"),
                Product.description.ilike(f"%{crop_type}%"),
                Product.category.ilike(f"%{crop_type}%")
            )
        ).offset(skip).limit(limit).all()

    # Order methods
    def create_order(self, consumer_id: int, order_data: OrderCreate) -> Optional[Order]:
        product = self.get_product(order_data.product_id)
        if not product or product.availability != AvailabilityStatus.IN_STOCK:
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
        return self.db.query(Order).filter(Order.consumer_id == user_id).order_by(Order.created_at.desc()).all()

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
        """Get total count of all approved and listed products"""
        return self.db.query(func.count(Product.id)).filter(
            Product.is_approved == True,
            Product.is_listed == True
        ).scalar() or 0