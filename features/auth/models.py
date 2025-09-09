from sqlalchemy import Boolean, Column, Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class UserCategory(str, enum.Enum):
    FARMER = "farmer"
    CONSUMER = "consumer"

class OTPMedium(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"

class OTPType(str, enum.Enum):
    VERIFICATION = "verification"
    PASSWORD_RESET = "password_reset"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone_number = Column(String, unique=True, index=True, nullable=True)
    password = Column(String)
    category = Column(Enum(UserCategory))
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    otp_codes = relationship("OTPCode", back_populates="user", cascade="all, delete-orphan")
    farmer_profile = relationship("FarmerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    consumer_profile = relationship("ConsumerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # marketplace relationships
    products = relationship("Product", back_populates="farmer", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="consumer", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="consumer", cascade="all, delete-orphan")

class OTPCode(Base):
    __tablename__ = "otp_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    code = Column(String, nullable=False)
    medium = Column(Enum(OTPMedium), nullable=False)
    otp_type = Column(Enum(OTPType), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_verified = Column(Boolean, default=False)  # Track if OTP has been verified
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="otp_codes")