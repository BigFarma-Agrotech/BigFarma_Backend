from pydantic import BaseModel, field_serializer
from typing import Optional
from datetime import datetime, timezone

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

    @field_serializer("created_at", "read_at")
    def _as_utc(self, value: Optional[datetime]) -> Optional[str]:
        # Times are stored in UTC; some databases (SQLite) hand them back without
        # an offset, which clients would read as local time
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

class UnreadCountResponse(BaseModel):
    unread_count: int
