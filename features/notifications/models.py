from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from database import Base
import enum

class NotificationType(str, enum.Enum):
    ORDER_PLACED = "order_placed"
    LOGIN_ALERT = "login_alert"

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Stored as a plain string so new types don't need a DB enum migration
    notification_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    # Optional pointer to the thing the notification is about, e.g. an order id
    reference_id = Column(Integer, nullable=True)

    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
