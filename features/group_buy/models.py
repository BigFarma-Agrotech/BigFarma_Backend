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
    chat = relationship("GroupChat", back_populates="group", uselist=False, cascade="all, delete-orphan")

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

class MessageType(str, enum.Enum):
    TEXT = "text"
    SYSTEM = "system"
    ANNOUNCEMENT = "announcement"
    JOIN_NOTIFICATION = "join_notification"
    LEAVE_NOTIFICATION = "leave_notification"
    PROGRESS_UPDATE = "progress_update"
    COMPLETION_NOTICE = "completion_notice"

class GroupChat(Base):
    __tablename__ = "group_chats"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("group_buys.id"), unique=True, nullable=False)
    
    # Chat status and lifecycle
    is_active = Column(Boolean, default=True)
    is_read_only = Column(Boolean, default=False)  # Set to True when group completes/cancels
    
    # Moderation settings
    allow_member_invite = Column(Boolean, default=True)
    auto_close_on_completion = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    group = relationship("GroupBuy", back_populates="chat")
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")
    memberships = relationship("ChatMembership", back_populates="chat", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("group_chats.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for system messages
    
    # Message content
    message_content = Column(Text, nullable=False)
    message_type = Column(Enum(MessageType), default=MessageType.TEXT)
    
    # Message metadata
    is_pinned = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_edited = Column(Boolean, default=False)
    pin_order = Column(Integer, nullable=True)  # Order of pinned messages
    
    # Threading and replies
    reply_to_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    thread_count = Column(Integer, default=0)  # Number of replies to this message
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    pinned_at = Column(DateTime(timezone=True), nullable=True)
    pinned_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    chat = relationship("GroupChat", back_populates="messages")
    user = relationship("User", foreign_keys=[user_id])
    pinned_by = relationship("User", foreign_keys=[pinned_by_user_id])
    reply_to = relationship("ChatMessage", remote_side=[id], backref="replies")

class ChatMembership(Base):
    __tablename__ = "chat_memberships"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("group_chats.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Membership status
    is_active = Column(Boolean, default=True)
    is_muted = Column(Boolean, default=False)
    is_moderator = Column(Boolean, default=False)  # Group creator is auto-moderator
    
    # Read tracking
    last_read_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    last_read_at = Column(DateTime(timezone=True), nullable=True)
    unread_count = Column(Integer, default=0)
    
    # Membership timeline
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)
    
    # Notifications preferences
    notify_on_mention = Column(Boolean, default=True)
    notify_on_all_messages = Column(Boolean, default=True)
    
    # Relationships
    chat = relationship("GroupChat", back_populates="memberships")
    user = relationship("User")
    last_read_message = relationship("ChatMessage", foreign_keys=[last_read_message_id])

class ChatReport(Base):
    __tablename__ = "chat_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("group_chats.id"), nullable=False)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    reported_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reported_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Report details
    report_reason = Column(String, nullable=False)  # spam, abuse, inappropriate, etc.
    report_description = Column(Text, nullable=True)
    
    # Report status
    status = Column(String, default="pending")  # pending, reviewed, resolved, dismissed
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Timestamps
    reported_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    chat = relationship("GroupChat")
    message = relationship("ChatMessage")
    reported_by = relationship("User", foreign_keys=[reported_by_user_id])
    reported_user = relationship("User", foreign_keys=[reported_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])