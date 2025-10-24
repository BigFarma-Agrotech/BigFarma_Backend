from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import re

# Enums for schemas
class GroupStatusEnum(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    LOCKED = "locked"

class GroupMemberStatusEnum(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    LEFT = "left"
    REMOVED = "removed"

# Base schemas
class GroupBuyBase(BaseModel):
    group_name: str = Field(..., min_length=3, max_length=100, description="Name of the group")
    group_description: Optional[str] = Field(None, max_length=500, description="Description of the group")
    group_location: str = Field(..., min_length=3, max_length=200, description="Location where the group will meet")
    product_id: int = Field(..., description="ID of the product to purchase")
    target_quantity: str = Field(..., description="Target quantity to purchase (e.g., '100kg', '50 pieces')")
    target_quantity_numeric: float = Field(..., gt=0, description="Numeric value of target quantity")
    quantity_unit: str = Field(..., description="Unit of measurement (e.g., 'kg', 'pieces', 'goats')")
    individual_contribution: float = Field(..., gt=0, description="Amount each member needs to contribute")

class GroupBuyCreate(BaseModel):
    group_name: str = Field(..., min_length=3, max_length=100, description="Name of the group")
    group_description: Optional[str] = Field(None, max_length=500, description="Description of the group")
    group_location: str = Field(..., min_length=3, max_length=200, description="Location where the group will meet")
    
    # More flexible product specification
    product_id: Optional[int] = Field(None, description="ID of the product to purchase")
    product_name: Optional[str] = Field(None, description="Name of the product (if product_id not provided)")
    
    # More flexible quantity specification
    target_quantity: str = Field(..., description="Target quantity to purchase (e.g., '100kg', '50 pieces')")
    target_quantity_numeric: Optional[float] = Field(None, gt=0, description="Numeric value of target quantity (auto-calculated if not provided)")
    quantity_unit: Optional[str] = Field(None, description="Unit of measurement (auto-extracted if not provided)")
    
    # Make individual_contribution optional with reasonable default calculation
    individual_contribution: Optional[float] = Field(None, gt=0, description="Amount each member needs to contribute (auto-calculated if not provided)")
    
    is_public: bool = Field(True, description="Whether group is publicly discoverable")
    max_members: Optional[int] = Field(None, gt=0, description="Optional member limit")
    deadline: Optional[datetime] = Field(None, description="Optional group deadline")
    
    @model_validator(mode='after')
    def validate_all_fields(self):
        """Validate and auto-calculate all fields after initial processing"""
        # Check product specification
        if not self.product_id and not self.product_name:
            raise ValueError("Either product_id or product_name must be provided")
        
        # Auto-calculate target_quantity_numeric if not provided
        if self.target_quantity_numeric is None:
            try:
                self.target_quantity_numeric = GroupBuyCreateValidator.validate_target_quantity(self.target_quantity, "")
            except:
                raise ValueError("Could not extract numeric value from target_quantity. Please provide target_quantity_numeric explicitly.")
        
        # Auto-extract quantity_unit if not provided
        if self.quantity_unit is None:
            # Try to extract unit from target_quantity string
            unit_match = re.search(r'([a-zA-Z]+)', self.target_quantity.lower())
            if unit_match:
                extracted_unit = unit_match.group(1)
                try:
                    self.quantity_unit = GroupBuyCreateValidator.validate_quantity_unit(extracted_unit)
                except:
                    # Default to 'pieces' if extraction fails
                    self.quantity_unit = 'pieces'
            else:
                # Default to 'pieces' if no unit found
                self.quantity_unit = 'pieces'
        
        return self

class GroupBuyUpdate(BaseModel):
    group_name: Optional[str] = Field(None, min_length=3, max_length=100)
    group_description: Optional[str] = Field(None, max_length=500)
    group_location: Optional[str] = Field(None, min_length=3, max_length=200)
    target_quantity: Optional[str] = None
    target_quantity_numeric: Optional[float] = Field(None, gt=0)
    quantity_unit: Optional[str] = None
    individual_contribution: Optional[float] = Field(None, gt=0)

class GroupBuyResponse(GroupBuyBase):
    id: int
    shareable_link: str
    creator_id: int
    status: GroupStatusEnum
    current_quantity: float
    progress_percentage: float
    group_wallet_balance: float
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]
    locked_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class GroupBuyDetailResponse(GroupBuyResponse):
    product: dict  # Product details
    creator: dict  # Creator details
    members: List[dict]  # Member details
    transactions: List[dict]  # Transaction history

# Member schemas
class GroupMemberBase(BaseModel):
    user_id: int
    quantity_committed: float = Field(..., gt=0, description="Quantity this member commits to")
    contribution_amount: float = Field(..., gt=0, description="Amount this member will contribute")

class GroupMemberCreate(GroupMemberBase):
    pass

class GroupMemberJoin(BaseModel):
    group_id: int
    quantity_committed: float = Field(..., gt=0)
    contribution_amount: float = Field(..., gt=0)

class GroupMemberResponse(GroupMemberBase):
    id: int
    group_id: int
    status: GroupMemberStatusEnum
    joined_at: Optional[datetime]
    left_at: Optional[datetime]
    invited_by: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Transaction schemas
class GroupTransactionBase(BaseModel):
    amount: float = Field(..., gt=0)
    transaction_type: str = Field(..., description="Type of transaction: contribution, refund, purchase")
    payment_method: Optional[str] = Field(None, description="Payment method used")
    payment_reference: Optional[str] = Field(None, description="External payment reference")

class GroupTransactionCreate(GroupTransactionBase):
    group_id: int
    member_id: int

class GroupTransactionResponse(GroupTransactionBase):
    id: int
    group_id: int
    member_id: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Notification schemas
class GroupNotificationBase(BaseModel):
    notification_type: str = Field(..., description="Type of notification")
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=1000)

class GroupNotificationCreate(GroupNotificationBase):
    group_id: int
    user_id: int

class GroupNotificationResponse(GroupNotificationBase):
    id: int
    group_id: int
    user_id: int
    is_read: bool
    sent_at: datetime
    
    class Config:
        from_attributes = True

# Share and invite schemas
class GroupInviteRequest(BaseModel):
    group_id: int
    email: Optional[str] = Field(None, description="Email to invite")
    phone: Optional[str] = Field(None, description="Phone number to invite")
    message: Optional[str] = Field(None, max_length=500, description="Custom invitation message")

class GroupInviteResponse(BaseModel):
    invitation_link: str
    invitation_token: str
    expires_at: datetime

# Progress and analytics schemas
class GroupProgressResponse(BaseModel):
    group_id: int
    current_quantity: float
    target_quantity: float
    progress_percentage: float
    members_count: int
    total_contributions: float
    days_remaining: Optional[int]
    estimated_completion_date: Optional[datetime]

class GroupAnalyticsResponse(BaseModel):
    total_groups_created: int
    active_groups: int
    completed_groups: int
    total_members: int
    total_transactions: float
    average_group_size: float
    success_rate: float

# Stock monitoring schemas
class StockAlertRequest(BaseModel):
    group_id: int
    alert_type: str = Field(..., description="Type of alert: low_stock, out_of_stock, price_change")
    message: str = Field(..., max_length=500)

class AlternativeProductSuggestion(BaseModel):
    product_id: int
    product_name: str
    price: float
    availability: str
    similarity_score: float
    reason: str

class StockAlertResponse(BaseModel):
    group_id: int
    alert_type: str
    message: str
    suggested_alternatives: List[AlternativeProductSuggestion]
    created_at: datetime

# Group Discovery and Joining Schemas
class GroupDiscoveryRequest(BaseModel):
    location: Optional[str] = Field(None, description="Filter by location")
    product_name: Optional[str] = Field(None, description="Search by product name")
    category: Optional[str] = Field(None, description="Filter by product category")
    min_price: Optional[float] = Field(None, gt=0, description="Minimum price filter")
    max_price: Optional[float] = Field(None, gt=0, description="Maximum price filter")
    sort_by: Optional[str] = Field("newest", description="Sort by: newest, oldest, price_asc, price_desc, progress")

class GroupPublicResponse(BaseModel):
    id: int
    group_name: str
    group_description: Optional[str]
    group_location: str
    product_name: str
    product_category: str
    product_price: float
    target_quantity: str
    quantity_unit: str
    progress_percentage: float
    current_quantity: float
    target_quantity_numeric: float
    slots_remaining: int
    max_members: Optional[int]
    members_count: int
    individual_contribution: float
    deadline: Optional[datetime]
    created_at: datetime
    is_public: bool
    
    class Config:
        from_attributes = True

class GroupJoinRequest(BaseModel):
    group_id: int
    quantity_requested: float = Field(..., gt=0, description="Quantity user wants to commit to")
    contribution_amount: float = Field(..., gt=0, description="Amount user will contribute")
    payment_method: str = Field("wallet", description="Payment method: wallet, card, bank_transfer")

class GroupJoinResponse(BaseModel):
    id: int
    group_id: int
    user_id: int
    quantity_requested: float
    contribution_amount: float
    payment_status: str
    payment_method: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class GroupPricingRequest(BaseModel):
    group_id: int
    quantity: float = Field(..., gt=0, description="Quantity to calculate price for")

class GroupPricingResponse(BaseModel):
    group_id: int
    quantity: float
    unit_price: float
    total_price: float
    discount_percentage: float
    savings_amount: float

class GroupJoinValidationRequest(BaseModel):
    group_id: int
    user_id: int

class GroupJoinValidationResponse(BaseModel):
    can_join: bool
    reason: Optional[str] = None
    slots_available: int
    max_members: Optional[int]
    deadline: Optional[datetime]
    conflicts: List[str] = []

# Validation methods
class GroupBuyCreateValidator:
    @staticmethod
    def validate_quantity_unit(quantity_unit: str) -> str:
        """Validate and normalize quantity unit"""
        valid_units = ["kg", "g", "pieces", "units", "goats", "cows", "chickens", "liters", "ml"]
        if quantity_unit.lower() not in valid_units:
            raise ValueError(f"Invalid quantity unit. Must be one of: {', '.join(valid_units)}")
        return quantity_unit.lower()
    
    @staticmethod
    def validate_target_quantity(target_quantity: str, quantity_unit: str) -> float:
        """Extract numeric value from target quantity string"""
        import re
        # Extract number from string like "100kg", "50 pieces"
        match = re.search(r'(\d+(?:\.\d+)?)', target_quantity)
        if not match:
            raise ValueError("Invalid target quantity format. Must contain a number.")
        return float(match.group(1))

# ========================
# CHAT SCHEMAS
# ========================

class MessageTypeEnum(str, Enum):
    TEXT = "text"
    SYSTEM = "system"
    ANNOUNCEMENT = "announcement"
    JOIN_NOTIFICATION = "join_notification"
    LEAVE_NOTIFICATION = "leave_notification"
    PROGRESS_UPDATE = "progress_update"
    COMPLETION_NOTICE = "completion_notice"

# Chat base schemas
class GroupChatBase(BaseModel):
    group_id: int
    is_active: bool = True
    is_read_only: bool = False
    allow_member_invite: bool = True
    auto_close_on_completion: bool = True

class GroupChatCreate(GroupChatBase):
    pass

class GroupChatResponse(GroupChatBase):
    id: int
    created_at: datetime
    closed_at: Optional[datetime]
    last_message_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class GroupChatDetailResponse(GroupChatResponse):
    group: dict  # Group details
    members_count: int
    unread_count: int
    pinned_messages: List[dict]
    recent_messages: List[dict]

# Message schemas
class ChatMessageBase(BaseModel):
    message_content: str = Field(..., min_length=1, max_length=2000, description="Message content")
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    reply_to_message_id: Optional[int] = None

class ChatMessageCreate(ChatMessageBase):
    chat_id: int

class ChatMessageSend(BaseModel):
    message_content: str = Field(..., min_length=1, max_length=2000)
    reply_to_message_id: Optional[int] = None

class ChatMessageResponse(ChatMessageBase):
    id: int
    chat_id: int
    user_id: Optional[int]
    is_pinned: bool
    is_deleted: bool
    is_edited: bool
    pin_order: Optional[int]
    thread_count: int
    created_at: datetime
    edited_at: Optional[datetime]
    pinned_at: Optional[datetime]
    pinned_by_user_id: Optional[int]
    
    # User details
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    
    # Reply details
    reply_to: Optional[dict] = None
    
    class Config:
        from_attributes = True

class ChatMessageUpdate(BaseModel):
    message_content: str = Field(..., min_length=1, max_length=2000)

class ChatMessagePin(BaseModel):
    is_pinned: bool
    pin_order: Optional[int] = None

# Chat membership schemas
class ChatMembershipBase(BaseModel):
    chat_id: int
    user_id: int
    is_active: bool = True
    is_muted: bool = False
    is_moderator: bool = False

class ChatMembershipCreate(ChatMembershipBase):
    pass

class ChatMembershipResponse(ChatMembershipBase):
    id: int
    last_read_message_id: Optional[int]
    last_read_at: Optional[datetime]
    unread_count: int
    joined_at: datetime
    left_at: Optional[datetime]
    notify_on_mention: bool
    notify_on_all_messages: bool
    
    # User details
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    
    class Config:
        from_attributes = True

class ChatMembershipUpdate(BaseModel):
    is_muted: Optional[bool] = None
    notify_on_mention: Optional[bool] = None
    notify_on_all_messages: Optional[bool] = None

# WebSocket message schemas
class WebSocketMessageType(str, Enum):
    MESSAGE = "message"
    TYPING = "typing"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    MESSAGE_PINNED = "message_pinned"
    MESSAGE_UNPINNED = "message_unpinned"
    MESSAGE_DELETED = "message_deleted"
    CHAT_CLOSED = "chat_closed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"

class WebSocketMessage(BaseModel):
    type: WebSocketMessageType
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[int] = None
    chat_id: Optional[int] = None

class TypingIndicator(BaseModel):
    user_id: int
    user_name: str
    is_typing: bool

# Message history and pagination
class MessageHistoryRequest(BaseModel):
    limit: int = Field(50, ge=1, le=100, description="Number of messages to retrieve")
    before_message_id: Optional[int] = Field(None, description="Get messages before this message ID")
    after_message_id: Optional[int] = Field(None, description="Get messages after this message ID")
    include_deleted: bool = Field(False, description="Include deleted messages")
    message_type: Optional[MessageTypeEnum] = Field(None, description="Filter by message type")

class MessageHistoryResponse(BaseModel):
    messages: List[ChatMessageResponse]
    has_more: bool
    total_count: int
    next_cursor: Optional[int] = None
    prev_cursor: Optional[int] = None

# Chat moderation schemas
class ChatReportCreate(BaseModel):
    message_id: int
    report_reason: str = Field(..., description="Reason for reporting")
    report_description: Optional[str] = Field(None, max_length=500, description="Detailed description")

class ChatReportResponse(BaseModel):
    id: int
    chat_id: int
    message_id: int
    reported_by_user_id: int
    reported_user_id: int
    report_reason: str
    report_description: Optional[str]
    status: str
    reported_at: datetime
    reviewed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ChatModerationAction(BaseModel):
    action: str = Field(..., description="Moderation action: mute, unmute, remove, warn")
    user_id: int = Field(..., description="Target user ID")
    duration_minutes: Optional[int] = Field(None, description="Duration for temporary actions")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for action")

# Chat analytics and stats
class ChatStatsResponse(BaseModel):
    chat_id: int
    total_messages: int
    active_members: int
    messages_today: int
    most_active_user: Optional[dict] = None
    average_response_time: Optional[float] = None
    pinned_messages_count: int

# Bulk operations
class BulkMessageOperation(BaseModel):
    message_ids: List[int] = Field(..., min_items=1, max_items=50)
    operation: str = Field(..., description="Operation: delete, pin, unpin")

class ChatSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=100, description="Search query")
    message_type: Optional[MessageTypeEnum] = None
    user_id: Optional[int] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(20, ge=1, le=50)

class ChatSearchResponse(BaseModel):
    messages: List[ChatMessageResponse]
    total_results: int
    search_time_ms: float