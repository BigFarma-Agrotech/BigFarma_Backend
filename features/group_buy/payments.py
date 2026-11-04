"""Paying to join a group buy, through Paystack.

A buyer picks a quantity (up to what the group still needs) and pays for it:
quantity x the product's price, plus tax. They become an active member only when
Paystack confirms the payment (verify call or webhook, via PaymentService); a
failed or abandoned payment frees the slot. Paid money sits in the group's wallet
(escrow). When paid quantities reach the target, the group completes and one
bulk order, already paid, goes to the farmer for delivery to the group.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from config import settings
from features.auth.models import User
from features.group_buy.models import GroupBuy, GroupMember, GroupMemberStatus, GroupStatus, GroupTransaction
from features.marketplace.models import (
    AvailabilityStatus, Order, OrderPaymentStatus, OrderStatus, Payment, PaymentStatus,
)
from features.notifications.models import NotificationType
from features.notifications.service import NotificationService
from features.orders.models import OrderTimelineStatus
from features.payments import paystack
from features.marketplace.stock import adjust_stock
from features.payments.service import CheckoutError, _allowed_callback, _payment_email, _reference
from utils.units import format_quantity, is_count_unit, unit_label

logger = logging.getLogger(__name__)

PURPOSE = "group_buy"


class GroupCheckoutRequest(BaseModel):
    quantity: float = Field(..., gt=0)
    # Where the farmer delivers this member's share; needed when joining. A member
    # topping up keeps the address they gave before.
    delivery_address: Optional[str] = Field(None, max_length=300)
    # Name and phone come from the member's profile; these are only used when the
    # profile has none (older clients still send them)
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    callback_url: str

    @field_validator("delivery_address", "contact_name", "contact_phone", "email")
    @classmethod
    def blank_is_none(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v and v.strip() else None


def unit_price(group: GroupBuy) -> float:
    """What one unit costs members: the product's (discounted) price."""
    product = group.product
    return round(product.price * (1 - (product.discount_percentage or 0) / 100), 2)


def remaining_quantity(group: GroupBuy) -> float:
    return max(round((group.target_quantity_numeric or 0) - (group.current_quantity or 0), 6), 0)


def profile_name(user: User) -> Optional[str]:
    """The member's full name from their consumer or farmer profile."""
    consumer = getattr(user, "consumer_profile", None)
    if consumer:
        name = " ".join(filter(None, [consumer.first_name, consumer.last_name])).strip()
        if name:
            return name
    farmer = getattr(user, "farmer_profile", None)
    if farmer and (farmer.full_name or "").strip():
        return farmer.full_name.strip()
    return None


def join_minimum(group: GroupBuy) -> float:
    """The least a new member may buy: the group's minimum share, or whatever is
    left when that's less."""
    return min(group.min_member_quantity or 1, remaining_quantity(group))


class GroupPaymentService:
    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------- joining / topping up
    async def start_checkout(self, user: User, group: GroupBuy, data: GroupCheckoutRequest) -> tuple:
        """Start a Paystack payment for a share of the group: a new member's first
        share (reserved as a pending member) or an existing member's top-up.
        Returns (payment, authorization_url)."""
        if not _allowed_callback(data.callback_url):
            raise CheckoutError("Invalid return address for payment.")
        if not paystack.is_configured():
            raise CheckoutError("Payments are not available right now. Please try again later.", 503)
        if group.status != GroupStatus.ACTIVE:
            raise CheckoutError("This group is no longer taking payments.")
        if group.deadline and group.deadline.replace(tzinfo=None) < datetime.utcnow():
            raise CheckoutError("This group's deadline has passed.")
        product = group.product
        if not product or product.availability != AvailabilityStatus.IN_STOCK or not product.is_listed:
            raise CheckoutError("This product is no longer available.")

        members = self.db.query(GroupMember).filter(GroupMember.group_id == group.id).all()
        mine = [m for m in members if m.user_id == user.id]
        existing = next((m for m in mine if m.status == GroupMemberStatus.ACTIVE), None)
        active = [m for m in members if m.status == GroupMemberStatus.ACTIVE]

        unit = group.quantity_unit or product.unit
        remaining = remaining_quantity(group)
        if is_count_unit(unit) and not float(data.quantity).is_integer():
            raise CheckoutError(f"Choose a whole number of {unit_label(2, unit)}.")
        if data.quantity > remaining + 1e-9:
            raise CheckoutError(f"The group only needs {format_quantity(remaining, unit)} more.")
        # Paid shares are taken out of stock, so what's left must cover this one
        stock = product.available_quantity
        if stock is not None and data.quantity > stock + 1e-9:
            raise CheckoutError(f"The farmer only has {format_quantity(stock, unit)} left in stock.")

        if existing:
            # Top-up: any amount up to what's left; no new slot is used
            member = existing
        else:
            if group.max_members and len(active) >= group.max_members:
                raise CheckoutError("This group is full.")
            # The profile is the source of truth for who the member is
            contact_name = profile_name(user) or data.contact_name
            contact_phone = (user.phone_number or "").strip() or data.contact_phone
            if not contact_name:
                raise CheckoutError("Add your name to your profile before joining a group.")
            if not contact_phone:
                raise CheckoutError("Add a phone number to your profile before joining a group.")
            if not data.delivery_address or len(data.delivery_address) < 5:
                raise CheckoutError("Enter the address the farmer should deliver your share to.")
            minimum = join_minimum(group)
            if data.quantity + 1e-9 < minimum:
                raise CheckoutError(f"Each member buys at least {format_quantity(minimum, unit)} in this group.")
            # The last free slot must take the rest, so a full group always reaches
            # its target (and closes) instead of being stuck with every slot taken
            if group.max_members and len(active) + 1 >= group.max_members and data.quantity + 1e-9 < remaining:
                raise CheckoutError(f"You're taking the last slot in this group, so your share must be the "
                                    f"remaining {format_quantity(remaining, unit)} to complete it.")
            # An earlier attempt the buyer abandoned: start over from it
            for old in (m for m in mine if m.status == GroupMemberStatus.PENDING):
                self._release(old, reason="replaced")
            member = GroupMember(
                group_id=group.id, user_id=user.id, status=GroupMemberStatus.PENDING,
                quantity_committed=0.0, contribution_amount=0.0,
                contact_name=contact_name, contact_phone=contact_phone,
                delivery_address=data.delivery_address,
            )
            self.db.add(member)
            self.db.flush()

        subtotal = round(data.quantity * unit_price(group), 2)
        tax = round(subtotal * settings.CHECKOUT_TAX_RATE, 2)
        amount = round(subtotal + tax, 2)
        payment = Payment(
            reference=_reference(), user_id=user.id, email=_payment_email(user, data.email),
            subtotal=subtotal, delivery_fee=0.0, tax=tax, amount=amount, amount_kobo=int(round(amount * 100)),
            status=PaymentStatus.PENDING.value, purpose=PURPOSE, group_member_id=member.id,
            group_quantity=data.quantity,
        )
        self.db.add(payment)
        self.db.commit()

        try:
            transaction = await paystack.initialize_transaction(
                email=payment.email, amount_kobo=payment.amount_kobo, reference=payment.reference,
                callback_url=data.callback_url,
                metadata={"user_id": user.id, "group": group.public_id, "top_up": bool(existing),
                          "quantity": format_quantity(data.quantity, unit)},
            )
            authorization_url = transaction.get("authorization_url")
            if not authorization_url:
                raise paystack.PaystackError("The payment service didn't return a payment page. Please try again.")
        except paystack.PaystackError as exc:
            payment.status = PaymentStatus.FAILED.value
            payment.gateway_response = exc.message
            if not existing:
                self._release(member, reason="payment failed")
            self.db.commit()
            raise CheckoutError(exc.message, exc.status_code)
        return payment, authorization_url

    # --------------------------------------------- called by PaymentService
    def payment_succeeded(self, payment: Payment, background_tasks: BackgroundTasks) -> None:
        """Paystack confirmed a payment: activate the new member, or add a top-up to
        their share, then update the group (closing it when the target is reached)."""
        member = payment.group_member
        if not member:
            logger.error("Group payment %s has no member", payment.reference)
            return
        group = member.group
        top_up = member.status == GroupMemberStatus.ACTIVE
        quantity = payment.group_quantity or 0
        if not top_up:
            member.status = GroupMemberStatus.ACTIVE
            member.joined_at = datetime.now(timezone.utc)
        member.quantity_committed = round((member.quantity_committed or 0) + quantity, 6)
        # The paid share is reserved from the product's stock
        if quantity:
            adjust_stock(self.db, group.product_id, -quantity)
        member.contribution_amount = round((member.contribution_amount or 0) + payment.subtotal, 2)
        self.db.add(GroupTransaction(
            group_id=group.id, member_id=member.id, amount=payment.subtotal,
            transaction_type="top_up" if top_up else "contribution", payment_method="paystack",
            payment_reference=payment.reference, status="completed",
            completed_at=datetime.now(timezone.utc),
        ))
        # Escrow holds the goods' value; tax isn't owed to the farmer
        group.group_wallet_balance = round((group.group_wallet_balance or 0) + payment.subtotal, 2)
        self._recalculate(group)
        self.db.commit()

        unit = group.quantity_unit or group.product.unit
        notifications = NotificationService(self.db)
        if top_up:
            self._notify(notifications, member.user_id, group, "Share topped up",
                         f"You added {format_quantity(quantity, unit)} in '{group.group_name}'. "
                         f"Your share is now {format_quantity(member.quantity_committed, unit)}.",
                         background_tasks)
        else:
            self._notify(notifications, member.user_id, group, "You're in the group!",
                         f"Your payment for {format_quantity(quantity, unit)} in "
                         f"'{group.group_name}' went through. We'll let you know when the group fills up.",
                         background_tasks)
            if group.creator_id != member.user_id:
                self._notify(notifications, group.creator_id, group, "New member joined",
                             f"Someone joined '{group.group_name}'. It's now {group.progress_percentage:.0f}% of the way there.",
                             background_tasks)

        if group.current_quantity + 1e-9 >= group.target_quantity_numeric:
            self._complete(group, background_tasks)

    def payment_failed(self, payment: Payment) -> None:
        """Payment failed or was abandoned: free a new member's reserved slot (a
        failed top-up leaves the member's existing share as it was)."""
        if payment.group_member and payment.group_member.status == GroupMemberStatus.PENDING:
            self._release(payment.group_member, reason="payment not completed")
            self.db.commit()

    # ------------------------------------------------------------- deadline
    async def expire_overdue_groups(self) -> int:
        """Close groups past their deadline that didn't reach the target, refunding every
        member through Paystack. Returns how many groups were expired."""
        now = datetime.now(timezone.utc)
        groups = self.db.query(GroupBuy).filter(
            GroupBuy.status == GroupStatus.ACTIVE, GroupBuy.deadline.isnot(None)
        ).all()
        expired = 0
        for group in groups:
            deadline = group.deadline if group.deadline.tzinfo else group.deadline.replace(tzinfo=timezone.utc)
            if deadline <= now:
                await self.expire_group(group)
                expired += 1
        return expired

    async def expire_group(self, group: GroupBuy) -> None:
        group.status = GroupStatus.CANCELLED
        self.db.commit()
        notifications = NotificationService(self.db)
        paid_members = [m for m in group.members if m.status == GroupMemberStatus.ACTIVE]
        for member in paid_members:
            payments = self.db.query(Payment).filter(
                Payment.group_member_id == member.id, Payment.status == PaymentStatus.SUCCESS.value
            ).all()
            refunded = bool(payments)
            for payment in payments:
                paid_back = False
                try:
                    await paystack.refund_transaction(payment.reference)
                    payment.status = "refunded"
                    paid_back = True
                except paystack.PaystackError as exc:
                    # Left for support to refund by hand; the member is told it's pending
                    payment.gateway_response = f"Refund failed: {exc.message}"
                    logger.error("Refund failed for %s (group %s): %s", payment.reference, group.public_id, exc.message)
                refunded = refunded and paid_back
                self.db.add(GroupTransaction(
                    group_id=group.id, member_id=member.id, amount=payment.subtotal,
                    transaction_type="refund", payment_method="paystack", payment_reference=payment.reference,
                    status="completed" if paid_back else "failed",
                    completed_at=datetime.now(timezone.utc) if paid_back else None,
                ))
                if paid_back:
                    group.group_wallet_balance = round((group.group_wallet_balance or 0) - payment.subtotal, 2)
            # The group never ordered, so the member's reserved share goes back on sale
            if member.quantity_committed:
                adjust_stock(self.db, group.product_id, member.quantity_committed)
            member.status = GroupMemberStatus.REMOVED
            member.left_at = datetime.now(timezone.utc)
            self.db.commit()
            message = (f"'{group.group_name}' didn't reach its target by the deadline, so it has closed. "
                       + ("Your payment has been refunded; it can take a few days to show."
                          if refunded else "Your refund is being processed; we'll contact you if needed."))
            try:
                notifications.create(member.user_id, NotificationType.GROUP_BUY, "Group closed: refund on the way",
                                     message, reference_id=group.id)
            except Exception:
                self.db.rollback()
                logger.exception("Failed to notify user %s about expired group %s", member.user_id, group.public_id)
        if group.creator_id not in {m.user_id for m in paid_members}:
            try:
                notifications.create(group.creator_id, NotificationType.GROUP_BUY, "Group closed",
                                     f"'{group.group_name}' reached its deadline without filling up, so it has closed.",
                                     reference_id=group.id)
            except Exception:
                self.db.rollback()
        logger.info("Group %s expired; %s member(s) refunded", group.public_id, len(paid_members))

    # ---------------------------------------------------------------- helpers
    def _release(self, member: GroupMember, reason: str) -> None:
        member.status = GroupMemberStatus.LEFT
        member.left_at = datetime.now(timezone.utc)
        logger.info("Released pending group member %s (%s)", member.id, reason)

    def _recalculate(self, group: GroupBuy) -> None:
        self.db.flush()
        active = self.db.query(GroupMember).filter(
            GroupMember.group_id == group.id, GroupMember.status == GroupMemberStatus.ACTIVE
        ).all()
        group.current_quantity = round(sum(m.quantity_committed or 0 for m in active), 6)
        target = group.target_quantity_numeric or 1
        group.progress_percentage = min(round(group.current_quantity / target * 100, 2), 100.0)

    def _complete(self, group: GroupBuy, background_tasks: BackgroundTasks) -> None:
        """Target reached: one paid bulk order to the farmer, delivered to the group."""
        from features.orders.service import OrderService

        product = group.product
        unit = group.quantity_unit or product.unit
        creator = self.db.get(User, group.creator_id)
        organiser = self.db.query(GroupMember).filter(
            GroupMember.group_id == group.id, GroupMember.user_id == group.creator_id,
            GroupMember.status == GroupMemberStatus.ACTIVE,
        ).first()
        contact = organiser or self.db.query(GroupMember).filter(
            GroupMember.group_id == group.id, GroupMember.status == GroupMemberStatus.ACTIVE
        ).first()

        # Each member's share goes to the address they gave when joining
        paid_members = [m for m in group.members if m.status == GroupMemberStatus.ACTIVE]
        drop_offs = "\n".join(
            f"- {m.contact_name or 'Member'} ({m.contact_phone or 'no phone'}): "
            f"{format_quantity(m.quantity_committed or 0, unit)} to "
            f"{m.delivery_address or group.group_location}"
            for m in paid_members
        )

        group.status = GroupStatus.COMPLETED
        group.completed_at = datetime.now(timezone.utc)
        order = Order(
            product_id=product.id,
            consumer_id=group.creator_id,
            quantity_ordered=format_quantity(group.current_quantity, unit),
            total_price=round(group.group_wallet_balance or 0, 2),
            delivery_address=(f"Group buy '{group.group_name}' ({group.group_location}): deliver each "
                              f"member's share to their address, listed in the delivery notes"),
            delivery_notes=f"{len(paid_members)} member(s):\n{drop_offs}" if paid_members else None,
            contact_phone=contact.contact_phone if contact else None,
            status=OrderStatus.PENDING,
            payment_status=OrderPaymentStatus.PAID,
            group_id=group.id,
            order_number=f"BFG{datetime.now().strftime('%Y%m%d')}{group.public_id.upper()}",
        )
        self.db.add(order)
        self.db.flush()
        OrderService(self.db)._create_timeline_entry(
            order.id, OrderTimelineStatus.PLACED, "Order Placed",
            f"Group '{group.group_name}' reached its target", True,
        )
        self.db.commit()
        logger.info("Group %s completed; bulk order %s placed", group.public_id, order.order_number)

        notifications = NotificationService(self.db)
        notifications._notify_farmer_new_order(order, background_tasks)
        member_ids = {m.user_id for m in group.members if m.status == GroupMemberStatus.ACTIVE} | {group.creator_id}
        for user_id in member_ids:
            self._notify(notifications, user_id, group, "Group target reached!",
                         f"'{group.group_name}' reached {format_quantity(group.target_quantity_numeric, unit)}. "
                         f"The order ({order.order_number}) has gone to the farmer for delivery.",
                         background_tasks)
        if creator is None:
            logger.warning("Group %s has no creator account", group.public_id)

    def _notify(self, notifications: NotificationService, user_id: int, group: GroupBuy,
                title: str, message: str, background_tasks: BackgroundTasks) -> None:
        try:
            notification = notifications.create(user_id, NotificationType.GROUP_BUY, title, message,
                                                reference_id=group.id)
            notifications.push_notification(notification, background_tasks)
        except Exception:
            self.db.rollback()
            logger.exception("Failed to send group notification to user %s", user_id)
