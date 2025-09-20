from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

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

class GroupBuyCreate(GroupBuyBase):
    is_public: bool = Field(True, description="Whether group is publicly discoverable")
    max_members: Optional[int] = Field(None, gt=0, description="Optional member limit")
    deadline: Optional[datetime] = Field(None, description="Optional group deadline")

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