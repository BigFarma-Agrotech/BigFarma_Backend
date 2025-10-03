import logging
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta
import uuid

# Import models from marketplace (existing) and orders (new)
from features.marketplace.models import Order, Product, OrderStatus, AvailabilityStatus
from features.orders.models import OrderTimeline, OrderIssue, OrderTimelineStatus, IssueStatus
from features.orders.schemas import (
    OrderIssueCreate, OrderStatusUpdate, OrderTimelineCreate, OrderFilter
)
from features.marketplace.schemas import OrderCreate
from features.users.models import FarmerProfile
from features.wallet.integration import WalletIntegration

logger = logging.getLogger(__name__)

class OrderService:
    def __init__(self, db: Session):
        self.db = db

    def create_order(self, consumer_id: int, order_data: OrderCreate) -> Optional[Order]:
        """Create a new order and record initial timeline."""
        product = self.db.query(Product).filter(Product.id == order_data.product_id).first()
        if not product or product.availability != AvailabilityStatus.IN_STOCK:
            logger.warning("Product %s not available for ordering", order_data.product_id)
            return None

        discounted_price = product.price * (1 - (product.discount_percentage or 0) / 100)

        from datetime import datetime
        import random
        import string

        date_part = datetime.now().strftime("%Y%m%d")
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        order_number = f"BF{date_part}{random_part}"

        order = Order(
            product_id=order_data.product_id,
            consumer_id=consumer_id,
            quantity_ordered=order_data.quantity_ordered,
            total_price=discounted_price,
            delivery_address=order_data.delivery_address,
            status=OrderStatus.PENDING,
            order_number=order_number,
            estimated_delivery_date=datetime.now() + timedelta(days=3),
        )

        self.db.add(order)
        self.db.flush()

        self._create_timeline_entry(
            order.id,
            OrderTimelineStatus.PLACED,
            "Order Placed",
            "Your order has been placed successfully",
            True,
        )

        self.db.commit()
        self.db.refresh(order)
        return order

    def get_user_orders(self, user_id: int, order_filter: Optional[OrderFilter] = None) -> List[Order]:
        """Get all orders for a user with optional filtering"""
        query = self.db.query(Order).filter(Order.consumer_id == user_id)
        
        # Apply filters
        if order_filter:
            if order_filter.status:
                query = query.filter(Order.status == order_filter.status)
            if order_filter.date_from:
                query = query.filter(Order.created_at >= order_filter.date_from)
            if order_filter.date_to:
                query = query.filter(Order.created_at <= order_filter.date_to)
            if order_filter.search:
                # Search by order number, product name, or farm name
                search_term = f"%{order_filter.search}%"
                query = query.join(Product).join(FarmerProfile, Product.farmer_id == FarmerProfile.user_id).filter(
                    Order.order_number.ilike(search_term) |
                    Product.name.ilike(search_term) |
                    FarmerProfile.farm_name.ilike(search_term)
                )
        
        return query.order_by(Order.created_at.desc()).all()

    def get_order_details(self, order_id: int, user_id: int) -> Optional[Order]:
        """Get detailed order information with all related data"""
        order = self.db.query(Order).options(
            joinedload(Order.product),
            joinedload(Order.consumer)
        ).filter(
            Order.id == order_id,
            Order.consumer_id == user_id
        ).first()
        
        return order

    def get_order_timeline(self, order_id: int, user_id: int) -> List[OrderTimeline]:
        """Get timeline for a specific order"""
        # First verify the user owns the order
        order = self.db.query(Order).filter(
            Order.id == order_id,
            Order.consumer_id == user_id
        ).first()
        
        if not order:
            return []
        
        return self.db.query(OrderTimeline).filter(
            OrderTimeline.order_id == order_id
        ).order_by(OrderTimeline.created_at.asc()).all()

    def get_order_issues(self, order_id: int, user_id: int) -> List[OrderIssue]:
        """Get all issues reported for an order"""
        return self.db.query(OrderIssue).join(Order).filter(
            Order.id == order_id,
            Order.consumer_id == user_id
        ).order_by(OrderIssue.created_at.desc()).all()

    def report_delivery_issue(self, order_id: int, user_id: int, issue_data: OrderIssueCreate) -> Optional[OrderIssue]:
        """Consumer reports a delivery issue"""
        # Verify the order belongs to the consumer
        order = self.db.query(Order).filter(
            Order.id == order_id,
            Order.consumer_id == user_id
        ).first()
        
        if not order:
            logger.warning(f"Order {order_id} not found for user {user_id}")
            return None
        
        # Create the issue report
        issue = OrderIssue(
            order_id=order_id,
            consumer_id=user_id,
            issue_description=issue_data.issue_description
        )
        
        # Update order status to reflect delivery issue
        order.status = OrderStatus.DELIVERY_ISSUE
        
        # Create timeline entry for the issue
        self._create_timeline_entry(
            order_id, 
            OrderTimelineStatus.AWAITING_CONFIRMATION, 
            "Delivery Issue - Pending review", 
            "We've logged your report. Support will contact you within 24-48 hours.",
            False
        )
        
        self.db.add(issue)
        self.db.commit()
        self.db.refresh(issue)
        
        logger.info(f"Delivery issue reported for order {order_id} by user {user_id}")
        return issue

    def confirm_delivery(self, order_id: int, user_id: int) -> Optional[Order]:
        """Consumer confirms they received their order"""
        order = self.db.query(Order).filter(
            Order.id == order_id,
            Order.consumer_id == user_id
        ).first()
        
        if not order:
            return None
        
        # Only allow confirmation if order is in awaiting confirmation status
        if order.status != OrderStatus.AWAITING_CONFIRMATION:
            logger.warning(f"Order {order_id} cannot be confirmed - current status: {order.status}")
            return None
        
        order.status = OrderStatus.DELIVERED

        # Credit the farmer's wallet for the completed sale
        product = order.product
        if product is not None:
            credited = WalletIntegration.credit_for_product_sale(
                db=self.db,
                farmer_id=product.farmer_id,
                amount=order.total_price,
                product_name=product.name,
                order_id=order.id,
            )
            if not credited:
                logger.warning(f"Failed to credit wallet for order {order_id}")
        else:
            logger.warning(f"Order {order_id} has no associated product for wallet credit")

        # Create timeline entry for delivery confirmation
        self._create_timeline_entry(
            order_id, 
            OrderTimelineStatus.DELIVERED, 
            "Delivery Confirmed", 
            "You have confirmed receipt of your order. Thank you! The farmer has been notified.",
            True
        )
        
        self.db.commit()
        self.db.refresh(order)
        
        logger.info(f"Order {order_id} delivery confirmed by user {user_id}")
        return order

    def update_order_status(self, order_id: int, status_update: OrderStatusUpdate) -> Optional[Order]:
        """Update order status (typically used by farmers/admin)"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None
        
        old_status = order.status
        order.status = status_update.status
        
        if status_update.delivery_notes:
            order.delivery_notes = status_update.delivery_notes
        
        # Create timeline entry for status change
        self._handle_status_change_timeline(order_id, status_update.status, old_status)
        
        self.db.commit()
        self.db.refresh(order)
        
        logger.info(f"Order {order_id} status updated from {old_status} to {status_update.status}")
        return order

    def create_timeline_entry(self, order_id: int, user_id: int, timeline_data: OrderTimelineCreate) -> Optional[OrderTimeline]:
        """Create a custom timeline entry"""
        # Verify the user has access to the order
        order = self.db.query(Order).filter(
            Order.id == order_id,
            Order.consumer_id == user_id
        ).first()
        
        if not order:
            return None
        
        timeline_entry = OrderTimeline(
            order_id=order_id,
            status=timeline_data.status,
            title=timeline_data.title,
            description=timeline_data.description,
            is_completed=timeline_data.is_completed,
            completed_at=datetime.now() if timeline_data.is_completed else None
        )
        
        self.db.add(timeline_entry)
        self.db.commit()
        self.db.refresh(timeline_entry)
        
        return timeline_entry

    # Helper methods
    def _create_timeline_entry(self, order_id: int, status: OrderTimelineStatus, title: str, 
                             description: str, is_completed: bool = False):
        """Create a timeline entry for an order"""
        timeline_entry = OrderTimeline(
            order_id=order_id,
            status=status,
            title=title,
            description=description,
            is_completed=is_completed,
            completed_at=datetime.now() if is_completed else None
        )
        
        self.db.add(timeline_entry)
        # Note: Don't commit here, let the calling method handle it

    def _handle_status_change_timeline(self, order_id: int, new_status: OrderStatus, old_status: OrderStatus):
        """Create appropriate timeline entries for status changes"""
        status_mappings = {
            OrderStatus.CONFIRMED: ("Order Confirmed", "Your order has been confirmed by the farmer"),
            OrderStatus.SHIPPING: ("Shipping In Progress", "Your order is on its way"),
            OrderStatus.AWAITING_CONFIRMATION: ("Awaiting Confirmation", "Please confirm if you received your order"),
            OrderStatus.DELIVERED: ("Delivered", "Order has been successfully delivered"),
            OrderStatus.CANCELLED: ("Order Cancelled", "Order has been cancelled"),
            OrderStatus.DELIVERY_ISSUE: ("Delivery Issue", "There was an issue with the delivery")
        }
        
        if new_status in status_mappings:
            title, description = status_mappings[new_status]
            timeline_status = self._get_timeline_status_from_order_status(new_status)
            is_completed = new_status in [OrderStatus.SHIPPING, OrderStatus.AWAITING_CONFIRMATION, OrderStatus.DELIVERED]
            
            self._create_timeline_entry(order_id, timeline_status, title, description, is_completed)

    def _get_timeline_status_from_order_status(self, order_status: OrderStatus) -> OrderTimelineStatus:
        """Map order status to timeline status"""
        mapping = {
            OrderStatus.PENDING: OrderTimelineStatus.PLACED,
            OrderStatus.CONFIRMED: OrderTimelineStatus.PLACED,
            OrderStatus.SHIPPING: OrderTimelineStatus.SHIPPING_IN_PROGRESS,
            OrderStatus.AWAITING_CONFIRMATION: OrderTimelineStatus.AWAITING_CONFIRMATION,
            OrderStatus.DELIVERED: OrderTimelineStatus.DELIVERED,
            OrderStatus.DELIVERY_ISSUE: OrderTimelineStatus.AWAITING_CONFIRMATION
        }
        return mapping.get(order_status, OrderTimelineStatus.PLACED)

    # Analytics methods
    def get_order_statistics(self, user_id: int) -> dict:
        """Get order statistics for a user"""
        orders = self.db.query(Order).filter(Order.consumer_id == user_id).all()
        
        stats = {
            "total_orders": len(orders),
            "pending_orders": len([o for o in orders if o.status == OrderStatus.PENDING]),
            "delivered_orders": len([o for o in orders if o.status == OrderStatus.DELIVERED]),
            "cancelled_orders": len([o for o in orders if o.status == OrderStatus.CANCELLED]),
            "total_spent": sum([o.total_price for o in orders if o.status != OrderStatus.CANCELLED]),
            "average_order_value": 0
        }
        
        if stats["total_orders"] > 0:
            stats["average_order_value"] = stats["total_spent"] / stats["total_orders"]
        
        return stats
