import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from features.auth.models import User
from features.marketplace.models import Order
from features.notifications.connection_manager import notification_manager
from features.notifications.models import Notification, NotificationType
from features.notifications.schemas import NotificationResponse
from services.email_service import email_service

logger = logging.getLogger(__name__)


def get_display_name(user: User) -> str:
    """Best available name for greeting a user; profiles hold names, not the user row."""
    if user.consumer_profile:
        return user.consumer_profile.first_name
    if user.farmer_profile:
        return user.farmer_profile.full_name
    return "there"


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, notification_type: NotificationType, title: str,
               message: str, reference_id: Optional[int] = None) -> Notification:
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type.value,
            title=title,
            message=message,
            reference_id=reference_id,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_user_notifications(self, user_id: int, unread_only: bool = False,
                               skip: int = 0, limit: int = 50) -> List[Notification]:
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read.is_(False))
        return query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(skip).limit(limit).all()

    def get_unread_count(self, user_id: int) -> int:
        return self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False)
        ).count()

    def mark_as_read(self, notification_id: int, user_id: int) -> Optional[Notification]:
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if not notification:
            return None
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_all_as_read(self, user_id: int) -> int:
        updated = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False)
        ).update({"is_read": True, "read_at": datetime.now(timezone.utc)}, synchronize_session=False)
        self.db.commit()
        return updated

    def push_notification(self, notification: Notification, background_tasks: BackgroundTasks) -> None:
        """Queue a real-time push of a new notification plus the updated unread count."""
        background_tasks.add_task(notification_manager.send_to_user, notification.user_id, {
            "type": "notification",
            "data": NotificationResponse.model_validate(notification).model_dump(mode="json"),
        })
        self.push_unread_count(notification.user_id, background_tasks)

    def push_unread_count(self, user_id: int, background_tasks: BackgroundTasks) -> None:
        """Queue a push of the unread count so badges stay in sync across tabs/devices."""
        background_tasks.add_task(notification_manager.send_to_user, user_id, {
            "type": "unread_count",
            "data": {"unread_count": self.get_unread_count(user_id)},
        })

    # Event hooks: write the in-app notification now (the request's DB session is
    # closed before background tasks run), and queue the push and email with plain values.

    def notify_order_placed(self, user: User, order: Order, background_tasks: BackgroundTasks) -> None:
        try:
            product_name = order.product.name if order.product else "your item"
            order_number = order.order_number or f"BF{order.id:06d}"
            notification = self.create(
                user.id,
                NotificationType.ORDER_PLACED,
                "Order placed successfully",
                f"Your order {order_number} for {product_name} has been placed.",
                reference_id=order.id,
            )
            self.push_notification(notification, background_tasks)
            if user.email:
                background_tasks.add_task(
                    email_service.send_order_confirmation_email,
                    to_email=user.email,
                    name=get_display_name(user),
                    order_number=order_number,
                    product_name=product_name,
                    quantity=order.quantity_ordered,
                    total_price=order.total_price,
                    delivery_address=order.delivery_address,
                    estimated_delivery_date=order.estimated_delivery_date,
                )
        except Exception:
            # Never fail the order because a notification couldn't be sent
            self.db.rollback()
            logger.exception("Failed to send order notifications for order %s", order.id)

    def notify_login(self, user: User, background_tasks: BackgroundTasks,
                     ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        try:
            login_time = datetime.now(timezone.utc)
            notification = self.create(
                user.id,
                NotificationType.LOGIN_ALERT,
                "New sign-in to your account",
                f"Your account was signed in to on {login_time:%d %b %Y at %H:%M} UTC. "
                "If this wasn't you, reset your password immediately.",
            )
            self.push_notification(notification, background_tasks)
            if user.email:
                background_tasks.add_task(
                    email_service.send_login_alert_email,
                    to_email=user.email,
                    name=get_display_name(user),
                    login_time=login_time,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
        except Exception:
            # Never block a login because a notification couldn't be sent
            self.db.rollback()
            logger.exception("Failed to send login notifications for user %s", user.id)
