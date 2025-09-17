import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from features.marketplace.models import Product, Order, Review, AvailabilityStatus, OrderStatus
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
        
        images_str = ",".join(product_data.images)
        
        product = Product(
            farmer_id=farmer_id,
            name=product_data.name,
            category=product_data.category,
            description=product_data.description,
            quantity=product_data.quantity,
            price=product_data.price,
            discount_percentage=product_data.discount_percentage,
            location=farmer_profile.farm_location,  # Use farm location from profile
            images=images_str
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
        if 'images' in update_dict:
            update_dict['images'] = ",".join(update_dict['images'])
        
        for key, value in update_dict.items():
            setattr(product, key, value)
        
        self.db.commit()
        self.db.refresh(product)
        return product

    def get_farmer_products(self, farmer_id: int) -> List[Product]:
        return self.db.query(Product).filter(Product.farmer_id == farmer_id).all()

    def get_product(self, product_id: int) -> Optional[Product]:
        return self.db.query(Product).filter(Product.id == product_id).first()

    def get_all_products(
        self, 
        skip: int = 0, 
        limit: int = 100,
        category: Optional[str] = None,
        search: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        location: Optional[str] = None,
        availability: Optional[str] = None,
        sort_by: Optional[str] = None
    ) -> List[Product]:
        query = self.db.query(Product).filter(
            Product.is_approved == True, 
            Product.is_listed == True
        )
        
        # Handle availability filter
        if availability == "in_stock":
            query = query.filter(Product.availability == AvailabilityStatus.IN_STOCK)
        elif availability == "out_of_stock":
            query = query.filter(Product.availability == AvailabilityStatus.OUT_OF_STOCK)
        elif availability != "all":
            # Default: only show in stock items
            query = query.filter(Product.availability == AvailabilityStatus.IN_STOCK)
        
        # Add filters
        if category:
            query = query.filter(Product.category == category)
        
        if search:
            # Search in name and description
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%")
                )
            )
        
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
            
        if max_price is not None:
            query = query.filter(Product.price <= max_price)
        
        if location:
            query = query.filter(Product.location.ilike(f"%{location}%"))
        
        # Sorting
        if sort_by == "price_asc":
            query = query.order_by(Product.price.asc())
        elif sort_by == "price_desc":
            query = query.order_by(Product.price.desc())
        elif sort_by == "rating":
            query = query.order_by(Product.average_rating.desc())
        elif sort_by == "newest":
            query = query.order_by(Product.created_at.desc())
        else:
            # Default: newest first
            query = query.order_by(Product.created_at.desc())
        
        return query.offset(skip).limit(limit).all()
    
    def get_products_count(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        location: Optional[str] = None,
        availability: Optional[str] = None
    ) -> int:
        """Get total count of products with filters"""
        query = self.db.query(func.count(Product.id)).filter(
            Product.is_approved == True, 
            Product.is_listed == True
        )
        
        # Handle availability filter
        if availability == "in_stock":
            query = query.filter(Product.availability == AvailabilityStatus.IN_STOCK)
        elif availability == "out_of_stock":
            query = query.filter(Product.availability == AvailabilityStatus.OUT_OF_STOCK)
        elif availability != "all":
            query = query.filter(Product.availability == AvailabilityStatus.IN_STOCK)
        
        if category:
            query = query.filter(Product.category == category)
        
        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%")
                )
            )
        
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
            
        if max_price is not None:
            query = query.filter(Product.price <= max_price)
        
        if location:
            query = query.filter(Product.location.ilike(f"%{location}%"))
        
        return query.scalar() or 0

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

    # Order methods
    def create_order(self, consumer_id: int, order_data: OrderCreate) -> Optional[Order]:
        product = self.get_product(order_data.product_id)
        if not product or product.availability != AvailabilityStatus.IN_STOCK:
            return None
        
        # Calculate total price with discount
        discounted_price = product.price * (1 - product.discount_percentage / 100)
        total_price = discounted_price  # This would need proper calculation based on quantity
        
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
        
        # Update product quantity (this would need proper quantity parsing)
        # For simplicity, we'll just mark as out of stock if this is the first order
        product.availability = AvailabilityStatus.OUT_OF_STOCK
        
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
        
        review = Review(
            product_id=review_data.product_id,
            consumer_id=consumer_id,
            rating=review_data.rating,
            comment=review_data.comment
        )
        
        # Update product ratings
        product.total_ratings += 1
        product.average_rating = (
            (product.average_rating * (product.total_ratings - 1) + review_data.rating) 
            / product.total_ratings
        )
        
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def get_product_reviews(self, product_id: int) -> List[Review]:
        return self.db.query(Review).filter(Review.product_id == product_id).order_by(Review.created_at.desc()).all()