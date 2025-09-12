from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

# Enums specific to order management
class IssueStatus(str, enum.Enum):
    REPORTED = "reported"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"

class OrderTimelineStatus(str, enum.Enum):
    PLACED = "placed"
    SHIPPING_IN_PROGRESS = "shipping_in_progress"
    DELIVERED_TO_CUSTOMER = "delivered_to_customer"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    DELIVERED = "delivered"

class OrderTimeline(Base):
    __tablename__ = "order_timeline"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    
    status = Column(Enum(OrderTimelineStatus), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship back to Order (defined in marketplace)
    # order = relationship("Order", back_populates="timeline")

class OrderIssue(Base):
    __tablename__ = "order_issues"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    consumer_id = Column(Integer, ForeignKey("users.id"))
    
    issue_description = Column(Text, nullable=False)
    status = Column(Enum(IssueStatus), default=IssueStatus.REPORTED)
    admin_response = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    # order = relationship("Order", back_populates="issues")
    consumer = relationship("User")
