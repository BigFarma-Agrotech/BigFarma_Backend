from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class ProductCategory(str, enum.Enum):
    CROP = "crop"
    LIVESTOCK = "livestock"

class AvailabilityStatus(str, enum.Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"

class ProductStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    OUT_OF_STOCK = "out_of_stock"
    UNLISTED = "unlisted"

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPING = "shipping"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    DELIVERY_ISSUE = "delivery_issue"

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"))
    
    # Product details
    name = Column(String, nullable=False)
    category = Column(Enum(ProductCategory), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    discount_percentage = Column(Float, default=0.0)
    location = Column(String, nullable=False)
    
    # Images (comma-separated URLs)
    images = Column(Text, nullable=False)
    
    is_approved = Column(Boolean, default=False)
    is_listed = Column(Boolean, default=True)
    availability = Column(Enum(AvailabilityStatus), default=AvailabilityStatus.IN_STOCK)
    
    total_ratings = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    farmer = relationship("User", back_populates="products")
    orders = relationship("Order", back_populates="product")
    reviews = relationship("Review", back_populates="product")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    consumer_id = Column(Integer, ForeignKey("users.id"))
    
    quantity_ordered = Column(String, nullable=False)
    total_price = Column(Float, nullable=False)
    delivery_address = Column(String, nullable=False)
    contact_phone = Column(String, nullable=True)
    delivery_notes = Column(Text, nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    
    # Enhanced order tracking
    order_number = Column(String, unique=True, nullable=True)  # Generated order number
    estimated_delivery_date = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="orders")
    consumer = relationship("User", back_populates="orders")

class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    consumer_id = Column(Integer, ForeignKey("users.id"))
    
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    product = relationship("Product", back_populates="reviews")
    consumer = relationship("User", back_populates="reviews")