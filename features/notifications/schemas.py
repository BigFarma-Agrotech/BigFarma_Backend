from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NotificationResponse(BaseModel):
    id: int
    notification_type: str
    title: str
    message: str
    reference_id: Optional[int] = None
    # Public ids of the referenced order and its product, for linking to it
    reference_public_id: Optional[str] = None
    product_public_id: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class UnreadCountResponse(BaseModel):
    unread_count: int
