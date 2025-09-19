from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum
import uuid

class GroupStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    LOCKED = "locked"  # When purchase is triggered

class GroupMemberStatus(str, enum.Enum):
    PENDING = "pending"  # Invited but not joined
    ACTIVE = "active"    # Joined and participating
    LEFT = "left"        # Left the group
    REMOVED = "removed"  # Removed by admin

class GroupBuy(Base):
    __tablename__ = "group_buys"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Group identification
    group_name = Column(String, nullable=False)
    group_description = Column(Text, nullable=True)
    group_location = Column(String, nullable=False)
    shareable_link = Column(String, unique=True, nullable=False)  # Unique shareable link
    
    # Product details
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    target_quantity = Column(String, nullable=False)  # e.g., "100kg", "50 pieces"
    target_quantity_numeric = Column(Float, nullable=False)  # Numeric value for calculations
    quantity_unit = Column(String, nullable=False)  # e.g., "kg", "pieces", "goats"
    
    # Group management
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(GroupStatus), default=GroupStatus.ACTIVE)
    is_public = Column(Boolean, default=True)  # Whether group is publicly discoverable
    max_members = Column(Integer, nullable=True)  # Optional member limit
    deadline = Column(DateTime(timezone=True), nullable=True)  # Optional group deadline
    
    # Progress tracking
    current_quantity = Column(Float, default=0.0)  # Current collected quantity
    progress_percentage = Column(Float, default=0.0)  # Calculated progress percentage
    
    # Financial
    group_wallet_balance = Column(Float, default=0.0)  # Total money collected
    individual_contribution = Column(Float, nullable=False)  # Amount each member needs to pay
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)  # When auto-purchase was triggered
    
    # Relationships
    product = relationship("Product")
    creator = relationship("User", foreign_keys=[creator_id])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    transactions = relationship("GroupTransaction", back_populates="group", cascade="all, delete-orphan")

class GroupMember(Base):
    __tablename__ = "group_members"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("group_buys.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Member details
    status = Column(Enum(GroupMemberStatus), default=GroupMemberStatus.PENDING)
    joined_at = Column(DateTime(timezone=True), nullable=True)
    left_at = Column(DateTime(timezone=True), nullable=True)
    
    # Contribution
    contribution_amount = Column(Float, default=0.0)  # Amount this member has contributed
    quantity_committed = Column(Float, default=0.0)  # Quantity this member committed to
    
    # Invitation details
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    invitation_token = Column(String, nullable=True)  # Unique token for invitation
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    group = relationship("GroupBuy", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    inviter = relationship("User", foreign_keys=[invited_by])

class GroupTransaction(Base):
    __tablename__ = "group_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("group_buys.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("group_members.id"), nullable=False)
    
    # Transaction details
    amount = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)  # "contribution", "refund", "purchase"
    payment_method = Column(String, nullable=True)  # "wallet", "card", "bank_transfer"
    payment_reference = Column(String, nullable=True)  # External payment reference
    
    # Status
    status = Column(String, default="pending")  # "pending", "completed", "failed", "refunded"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    group = relationship("GroupBuy", back_populates="transactions")
    member = relationship("GroupMember")

class GroupJoinRequest(Base):
    __tablename__ = "group_join_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("group_buys.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Join request details
    quantity_requested = Column(Float, nullable=False)  # Quantity user wants to commit to
    contribution_amount = Column(Float, nullable=False)  # Amount user will contribute
    
    # Payment details (placeholder for now)
    payment_status = Column(String, default="pending")  # pending, completed, failed, refunded
    payment_method = Column(String, nullable=True)  # wallet, card, bank_transfer
    payment_reference = Column(String, nullable=True)  # External payment reference
    
    # Status
    status = Column(String, default="pending")  # pending, approved, rejected, cancelled
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    group = relationship("GroupBuy")
    user = relationship("User")

class GroupNotification(Base):
    __tablename__ = "group_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("group_buys.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Notification details
    notification_type = Column(String, nullable=False)  # "group_created", "member_joined", "progress_update", "stock_alert", "purchase_triggered"
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    
    # Status
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    group = relationship("GroupBuy")
    user = relationship("User")