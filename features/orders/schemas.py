from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from features.marketplace.models import OrderStatus
from features.orders.models import IssueStatus, OrderTimelineStatus

# Enhanced Order schemas
class OrderDetailResponse(BaseModel):
    id: int
    order_number: str
    consumer_id: int
    product_id: int
    quantity_ordered: str
    total_price: float
    delivery_address: str
    contact_phone: Optional[str] = None
    delivery_notes: Optional[str] = None
    status: OrderStatus
    estimated_delivery_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Product information
    product_name: str
    farm_name: str
    farmer_name: str
    product_images: List[str] = []
    
    class Config:
        from_attributes = True

class OrderTimelineResponse(BaseModel):
    id: int
    status: OrderTimelineStatus
    title: str
    description: Optional[str] = None
    is_completed: bool
    completed_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrderIssueResponse(BaseModel):
    id: int
    issue_description: str
    status: IssueStatus
    admin_response: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class OrderWithDetailsResponse(OrderDetailResponse):
    timeline: List[OrderTimelineResponse] = []
    issues: List[OrderIssueResponse] = []

# Input schemas
class OrderIssueCreate(BaseModel):
    issue_description: str
    
    @validator('issue_description')
    def validate_description(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Issue description must be at least 10 characters long')
        return v.strip()

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    delivery_notes: Optional[str] = None

class OrderTimelineCreate(BaseModel):
    status: OrderTimelineStatus
    title: str
    description: Optional[str] = None
    is_completed: bool = False

# Search/Filter schemas
class OrderFilter(BaseModel):
    status: Optional[OrderStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None  # Search by order number, product name, farm name
