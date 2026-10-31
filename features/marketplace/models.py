from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from utils.public_id import generate_public_id
from utils.units import parse_quantity
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
    # Random ID used in URLs and the API instead of the guessable integer id
    public_id = Column(String(8), unique=True, index=True, nullable=False, default=generate_public_id)
    farmer_id = Column(Integer, ForeignKey("users.id"))
    
    # Product details
    name = Column(String, nullable=False)
    category = Column(Enum(ProductCategory), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(String, nullable=False)  # stock with its unit, e.g. "100 kg"
    # The unit the product is priced and sold in ("kg", "bag", "head", ...)
    unit = Column(String, nullable=True)
    # The least a buyer may order, in `unit`
    min_order_quantity = Column(Float, nullable=False, default=1.0, server_default="1")
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
    
    @property
    def available_quantity(self):
        """Stock as a number (None if `quantity` doesn't start with one)."""
        return parse_quantity(self.quantity)[0]

    # Relationships
    farmer = relationship("User", back_populates="products")
    orders = relationship("Order", back_populates="product")
    reviews = relationship("Review", back_populates="product")

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"      # sent to Paystack, not paid yet
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"  # the buyer left the Paystack page


class OrderPaymentStatus:
    # Plain strings (stored as String): only paid orders reach the farmer
    UNPAID = "unpaid"
    PAID = "paid"


class Payment(Base):
    """One Paystack transaction covering every order from a checkout."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    # Sent to Paystack as the transaction reference
    reference = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    email = Column(String, nullable=False)
    subtotal = Column(Float, nullable=False)
    delivery_fee = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False)          # naira, what the buyer pays
    amount_kobo = Column(Integer, nullable=False)   # what Paystack is asked to charge
    status = Column(String, nullable=False, default=PaymentStatus.PENDING.value)
    gateway_response = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)

    orders = relationship("Order", back_populates="payment")


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    # Random ID used in URLs and the API instead of the guessable integer id
    public_id = Column(String(8), unique=True, index=True, nullable=False, default=generate_public_id)
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
    # Orders exist from checkout but only count (and reach the farmer) once paid
    payment_status = Column(String, nullable=False, default=OrderPaymentStatus.UNPAID,
                            server_default=OrderPaymentStatus.UNPAID, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True, index=True)
    estimated_delivery_date = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="orders")
    consumer = relationship("User", back_populates="orders")
    payment = relationship("Payment", back_populates="orders")

    @property
    def product_public_id(self):
        return self.product.public_id if self.product else None

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