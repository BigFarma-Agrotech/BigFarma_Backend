import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from features.auth.models import User
from features.marketplace.models import Order, OrderStatus, Product
from features.notifications.connection_manager import notification_manager
from features.notifications.models import Notification, NotificationType
from features.notifications.schemas import NotificationResponse
from database import SessionLocal
from services.email_service import email_service
from services.login_context import describe_device, lookup_location

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

    def with_references(self, notifications: List[Notification]) -> List[Notification]:
        """Fill in the public ids of the orders the notifications point at (one query)."""
        order_ids = {
            n.reference_id for n in notifications
            if n.reference_id is not None and n.notification_type != NotificationType.LOGIN_ALERT.value
        }
        if not order_ids:
            return notifications
        rows = (
            self.db.query(Order.id, Order.public_id, Product.public_id)
            .join(Product, Order.product_id == Product.id)
            .filter(Order.id.in_(order_ids))
            .all()
        )
        public_ids = {order_id: (order_public_id, product_public_id)
                      for order_id, order_public_id, product_public_id in rows}
        for n in notifications:
            if n.notification_type != NotificationType.LOGIN_ALERT.value and n.reference_id in public_ids:
                n.reference_public_id, n.product_public_id = public_ids[n.reference_id]
        return notifications

    def get_user_notifications(self, user_id: int, unread_only: bool = False,
                               skip: int = 0, limit: int = 50) -> List[Notification]:
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read.is_(False))
        notifications = query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(skip).limit(limit).all()
        return self.with_references(notifications)

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
        return self.with_references([notification])[0]

    def mark_all_as_read(self, user_id: int) -> int:
        updated = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False)
        ).update({"is_read": True, "read_at": datetime.now(timezone.utc)}, synchronize_session=False)
        self.db.commit()
        return updated

    def push_notification(self, notification: Notification, background_tasks: BackgroundTasks) -> None:
        """Queue a real-time push of a new notification plus the updated unread count."""
        self.with_references([notification])
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

        # Separate try so a problem on one side doesn't stop the other
        self._notify_farmer_new_order(order, background_tasks)

    def _notify_farmer_new_order(self, order: Order, background_tasks: BackgroundTasks) -> None:
        try:
            product = order.product
            farmer = product.farmer if product else None
            if not farmer:
                return
            order_number = order.order_number or f"BF{order.id:06d}"
            notification = self.create(
                farmer.id,
                NotificationType.NEW_ORDER,
                "New order received",
                f"A buyer ordered {order.quantity_ordered} of {product.name} (order {order_number}). "
                "Confirm it from your orders page.",
                reference_id=order.id,
            )
            self.push_notification(notification, background_tasks)
            if farmer.email:
                background_tasks.add_task(
                    email_service.send_new_order_email,
                    to_email=farmer.email,
                    name=get_display_name(farmer),
                    order_number=order_number,
                    product_name=product.name,
                    quantity=order.quantity_ordered,
                    total_price=order.total_price,
                    delivery_address=order.delivery_address,
                    estimated_delivery_date=order.estimated_delivery_date,
                )
        except Exception:
            self.db.rollback()
            logger.exception("Failed to notify farmer about order %s", order.id)

    # Buyer-facing wording for each status a farmer can move an order to
    _STATUS_MESSAGES = {
        OrderStatus.CONFIRMED: ("Order confirmed", "The farmer has confirmed your order {number} for {product}."),
        OrderStatus.SHIPPING: ("Order on its way", "Your order {number} for {product} is on its way."),
        OrderStatus.AWAITING_CONFIRMATION: (
            "Did your order arrive?",
            "Your order {number} for {product} has been delivered. Please confirm you received it.",
        ),
        OrderStatus.CANCELLED: ("Order cancelled", "Your order {number} for {product} has been cancelled."),
    }

    def notify_order_status_changed(self, order: Order, background_tasks: BackgroundTasks) -> None:
        """Tell the buyer when the farmer updates their order."""
        try:
            template = self._STATUS_MESSAGES.get(order.status)
            if not template:
                return
            title, message = template
            product_name = order.product.name if order.product else "your item"
            notification = self.create(
                order.consumer_id,
                NotificationType.ORDER_STATUS,
                title,
                message.format(number=order.order_number or f"BF{order.id:06d}", product=product_name),
                reference_id=order.id,
            )
            self.push_notification(notification, background_tasks)
        except Exception:
            self.db.rollback()
            logger.exception("Failed to notify buyer about status change on order %s", order.id)

    def notify_delivery_confirmed(self, order: Order, background_tasks: BackgroundTasks) -> None:
        """Tell the farmer the buyer confirmed delivery and the sale was credited."""
        self._notify_farmer(
            order, background_tasks, NotificationType.DELIVERY_CONFIRMED,
            "Delivery confirmed",
            "The buyer confirmed delivery of order {number} for {product}. "
            "₦{amount:,.2f} has been added to your wallet.",
        )

    def notify_delivery_issue(self, order: Order, background_tasks: BackgroundTasks) -> None:
        """Tell the farmer the buyer reported a problem with delivery."""
        self._notify_farmer(
            order, background_tasks, NotificationType.DELIVERY_ISSUE,
            "Delivery issue reported",
            "The buyer reported a problem with order {number} for {product}. Our support team will follow up.",
        )

    def _notify_farmer(self, order: Order, background_tasks: BackgroundTasks,
                       notification_type: NotificationType, title: str, message: str) -> None:
        try:
            product = order.product
            if not product or not product.farmer_id:
                return
            notification = self.create(
                product.farmer_id,
                notification_type,
                title,
                message.format(
                    number=order.order_number or f"BF{order.id:06d}",
                    product=product.name,
                    amount=order.total_price or 0,
                ),
                reference_id=order.id,
            )
            self.push_notification(notification, background_tasks)
        except Exception:
            self.db.rollback()
            logger.exception("Failed to notify farmer (%s) for order %s", notification_type.value, order.id)

    def notify_login(self, user: User, background_tasks: BackgroundTasks,
                     ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Queue the login alert. Unlike the order hooks, all of it runs after the response,
        because finding the location means calling an outside service."""
        background_tasks.add_task(
            deliver_login_notifications,
            user_id=user.id,
            email=user.email,
            name=get_display_name(user),
            login_time=datetime.now(timezone.utc),
            ip_address=ip_address,
            user_agent=user_agent,
        )


async def deliver_login_notifications(user_id: int, email: Optional[str], name: str, login_time: datetime,
                                      ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> None:
    """Create, push and email the login alert. Runs as a background task, so it opens its
    own DB session (the request's one is already closed) and never raises."""
    device = describe_device(user_agent)
    location = await lookup_location(ip_address)

    details = " ".join(filter(None, [
        f"from {device}" if device else None,
        f"in {location}" if location else None,
    ]))
    message = (
        f"New sign-in {details + ' ' if details else ''}on {login_time:%d %b %Y at %H:%M} UTC. "
        "If this wasn't you, reset your password immediately."
    )

    db = SessionLocal()
    try:
        service = NotificationService(db)
        notification = service.create(user_id, NotificationType.LOGIN_ALERT, "New sign-in to your account", message)
        payload = NotificationResponse.model_validate(notification).model_dump(mode="json")
        unread_count = service.get_unread_count(user_id)
    except Exception:
        db.rollback()
        logger.exception("Failed to create login notification for user %s", user_id)
        payload = None
    finally:
        db.close()

    if payload:
        await notification_manager.send_to_user(user_id, {"type": "notification", "data": payload})
        await notification_manager.send_to_user(user_id, {"type": "unread_count", "data": {"unread_count": unread_count}})

    if email:
        await email_service.send_login_alert_email(
            to_email=email,
            name=name,
            login_time=login_time,
            ip_address=ip_address,
            device=device,
            location=location,
        )
