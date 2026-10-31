"""Checkout through Paystack.

Checkout creates the orders (unpaid) and one Payment for their total, then sends
the buyer to Paystack. When Paystack confirms the charge, through the verify call
the frontend makes on return or through the webhook, the payment and its orders
are marked paid and the buyer and farmers are notified. Unpaid orders never show
up for anyone.
"""
import logging
import secrets
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session, joinedload

from config import settings
from features.auth.models import User
from features.marketplace.models import (
    AvailabilityStatus, Order, OrderPaymentStatus, Payment, PaymentStatus, Product,
)
from features.marketplace.schemas import OrderCreate
from features.notifications.service import NotificationService
from features.orders.service import OrderService, order_quantity_problem
from features.marketplace.stock import adjust_stock
from utils.units import format_quantity
from features.payments import paystack
from features.payments.schemas import CheckoutRequest, PaymentOrder, PaymentResponse

logger = logging.getLogger(__name__)


class CheckoutError(Exception):
    """A checkout problem the buyer can fix; `message` is shown to them."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _allowed_callback(url: str) -> bool:
    parsed = urlparse(url)
    hosts = {h.strip().lower() for h in settings.PAYMENT_CALLBACK_HOSTS.split(",") if h.strip()}
    return parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in hosts


def _payment_email(user: User, requested: Optional[str]) -> str:
    """Paystack requires an email; accounts may have only a phone number."""
    if requested:
        return requested
    if user.email:
        return user.email
    return f"customer{user.id}@bigfarma.ng"


def _reference() -> str:
    return f"BFP-{secrets.token_hex(8).upper()}"


def payment_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        reference=payment.reference,
        status=payment.status,
        subtotal=payment.subtotal,
        delivery_fee=payment.delivery_fee,
        tax=payment.tax,
        amount=payment.amount,
        paid_at=payment.paid_at,
        gateway_response=payment.gateway_response,
        purpose=payment.purpose or "order",
        group_public_id=(payment.group_member.group.public_id
                         if payment.purpose == "group_buy" and payment.group_member else None),
        orders=[
            PaymentOrder(
                public_id=order.public_id,
                order_number=order.order_number or f"BF{order.id:06d}",
                product_name=order.product.name if order.product else "Product",
                quantity_ordered=order.quantity_ordered,
                total_price=order.total_price,
            )
            for order in sorted(payment.orders, key=lambda o: o.id)
        ],
    )


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    async def checkout(self, user: User, data: CheckoutRequest) -> tuple:
        """Create unpaid orders and a Paystack transaction; returns (payment, authorization_url)."""
        if not _allowed_callback(data.callback_url):
            raise CheckoutError("Invalid return address for payment.")
        if not paystack.is_configured():
            raise CheckoutError("Payments are not available right now. Please try again later.", 503)

        # Check every item first so nothing is created when one can't be bought
        products = {
            p.id: p for p in self.db.query(Product).filter(
                Product.id.in_([item.product_id for item in data.items])
            )
        }
        unavailable = [
            products[item.product_id].name if item.product_id in products else f"Product {item.product_id}"
            for item in data.items
            if item.product_id not in products
            or products[item.product_id].availability != AvailabilityStatus.IN_STOCK
            or not products[item.product_id].is_listed
        ]
        if unavailable:
            raise CheckoutError(f"No longer available: {', '.join(unavailable)}. Remove it from your cart to continue.")

        # Minimum order, stock and whole units (bags, head, ...) per product
        problems = [order_quantity_problem(products[item.product_id], item.quantity) for item in data.items]
        problems = [p for p in problems if p]
        if problems:
            raise CheckoutError(". ".join(problems) + ". Update your cart to continue.")

        delivery_address = f"{data.delivery_address} (Contact: {data.contact_name}, {data.contact_phone})"
        if data.delivery_option == "pickup":
            delivery_address = f"Pickup - {delivery_address}"

        payment = Payment(
            reference=_reference(),
            user_id=user.id,
            email=_payment_email(user, data.email),
            subtotal=0, delivery_fee=0, tax=0, amount=0, amount_kobo=0,
            status=PaymentStatus.PENDING.value,
        )
        self.db.add(payment)
        self.db.flush()

        order_service = OrderService(self.db)
        orders: List[Order] = []
        for item in data.items:
            # Stored with the unit so the farmer sees "5 kg", not "5"
            quantity = format_quantity(item.quantity, products[item.product_id].unit)
            order = order_service.create_order(
                user.id,
                OrderCreate(product_id=item.product_id, quantity_ordered=quantity, delivery_address=delivery_address),
                contact_phone=data.contact_phone,
                payment_id=payment.id,
                commit=False,
            )
            if order is None:
                self.db.rollback()
                raise CheckoutError(f"{products[item.product_id].name} couldn't be ordered. Check the quantity and try again.")
            orders.append(order)

        # The server's prices decide what's charged, not the cart's
        subtotal = round(sum(order.total_price for order in orders), 2)
        delivery_fee = settings.CHECKOUT_DELIVERY_FEE if data.delivery_option == "door-delivery" else 0.0
        tax = round(subtotal * settings.CHECKOUT_TAX_RATE, 2)
        amount = round(subtotal + delivery_fee + tax, 2)
        payment.subtotal, payment.delivery_fee, payment.tax, payment.amount = subtotal, delivery_fee, tax, amount
        payment.amount_kobo = int(round(amount * 100))
        self.db.commit()

        try:
            transaction = await paystack.initialize_transaction(
                email=payment.email,
                amount_kobo=payment.amount_kobo,
                reference=payment.reference,
                callback_url=data.callback_url,
                metadata={
                    "user_id": user.id,
                    "orders": [order.order_number for order in orders],
                },
            )
        except paystack.PaystackError as exc:
            payment.status = PaymentStatus.FAILED.value
            payment.gateway_response = exc.message
            self.db.commit()
            raise CheckoutError(exc.message, exc.status_code)

        authorization_url = transaction.get("authorization_url")
        if not authorization_url:
            payment.status = PaymentStatus.FAILED.value
            self.db.commit()
            raise CheckoutError("The payment service didn't return a payment page. Please try again.", 502)

        self.db.refresh(payment)
        return payment, authorization_url

    def get_payment(self, reference: str, user_id: Optional[int] = None) -> Optional[Payment]:
        query = self.db.query(Payment).options(
            joinedload(Payment.orders).joinedload(Order.product)
        ).filter(Payment.reference == reference)
        if user_id is not None:
            query = query.filter(Payment.user_id == user_id)
        return query.first()

    async def verify(self, payment: Payment, background_tasks: BackgroundTasks) -> Payment:
        """Ask Paystack for the transaction's status and apply it. Safe to call repeatedly."""
        if payment.status == PaymentStatus.SUCCESS.value:
            return payment
        transaction = await paystack.verify_transaction(payment.reference)
        return self.apply_transaction(payment, transaction, background_tasks)

    def apply_transaction(self, payment: Payment, transaction: dict,
                          background_tasks: BackgroundTasks) -> Payment:
        """Record a Paystack transaction result on the payment (and its orders when paid)."""
        # Lock the row: the buyer's verify call and Paystack's webhook can land
        # together, and the orders must only be marked paid (and announced) once
        payment = self.db.query(Payment).filter(Payment.id == payment.id).with_for_update().populate_existing().one()
        if payment.status == PaymentStatus.SUCCESS.value:
            return payment

        status = transaction.get("status")
        payment.gateway_response = transaction.get("gateway_response") or payment.gateway_response

        if status == "success":
            amount_ok = int(transaction.get("amount") or 0) == payment.amount_kobo
            currency_ok = (transaction.get("currency") or "NGN") == "NGN"
            if not (amount_ok and currency_ok):
                # Never mark paid on a mismatched charge; needs a human to look at it
                logger.error("Paystack amount mismatch for %s: %s", payment.reference, transaction)
                payment.status = PaymentStatus.FAILED.value
                payment.gateway_response = "Amount paid doesn't match the order total. Contact support."
                self.db.commit()
                self._payment_failed(payment)
                return payment
            self._mark_paid(payment, background_tasks)
        elif status in (PaymentStatus.FAILED.value, PaymentStatus.ABANDONED.value, "reversed"):
            payment.status = PaymentStatus.ABANDONED.value if status == "abandoned" else PaymentStatus.FAILED.value
            self.db.commit()
            self._payment_failed(payment)
        else:
            # ongoing / pending / queued: leave it pending and let the buyer check again
            self.db.commit()
        return payment

    def _payment_failed(self, payment: Payment) -> None:
        if payment.purpose == "group_buy":
            from features.group_buy.payments import GroupPaymentService
            GroupPaymentService(self.db).payment_failed(payment)

    def _mark_paid(self, payment: Payment, background_tasks: BackgroundTasks) -> None:
        payment.status = PaymentStatus.SUCCESS.value
        payment.paid_at = datetime.now(timezone.utc)
        if payment.purpose == "group_buy":
            self.db.commit()
            from features.group_buy.payments import GroupPaymentService
            GroupPaymentService(self.db).payment_succeeded(payment, background_tasks)
            return
        for order in payment.orders:
            order.payment_status = OrderPaymentStatus.PAID
            # Paid orders take their quantity out of the product's stock
            units = OrderService._parse_units(order.quantity_ordered)
            if units:
                adjust_stock(self.db, order.product_id, -units)
        self.db.commit()
        self.db.refresh(payment)
        logger.info("Payment %s confirmed for %s order(s)", payment.reference, len(payment.orders))

        # Only now do the buyer and the farmers hear about the orders
        buyer = self.db.get(User, payment.user_id)
        notifications = NotificationService(self.db)
        for order in payment.orders:
            notifications.notify_order_placed(buyer, order, background_tasks)
