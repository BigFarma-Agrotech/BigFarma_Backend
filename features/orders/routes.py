from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from database import get_db
from features.orders.schemas import (
    OrderDetailResponse, OrderWithDetailsResponse, OrderTimelineResponse, 
    OrderIssueResponse, OrderIssueCreate, OrderStatusUpdate, OrderFilter,
    FarmerOrderResponse, FarmerOrderListResponse
)
from features.orders.service import OrderService, InvalidStatusTransition
from features.notifications.service import NotificationService
from features.marketplace.models import Order, Product, OrderStatus
from features.users.models import FarmerProfile
from features.auth.models import User, UserCategory
from utils.product_images import public_images
from utils.public_id import resolve_id
from core.dependencies import get_current_active_user

router = APIRouter(prefix="/orders", tags=["Orders"])


def _farmer_order_response(order: Order, farmer_profile: Optional[FarmerProfile]) -> FarmerOrderResponse:
    """An order as the selling farmer sees it, including the buyer's contact details."""
    product = order.product
    consumer = order.consumer
    consumer_profile = consumer.consumer_profile if consumer else None

    return FarmerOrderResponse(
        id=order.id,
        public_id=order.public_id,
        order_number=order.order_number if order.order_number else f"BF{order.id:06d}",
        consumer_id=order.consumer_id,
        product_id=order.product_id,
        product_public_id=order.product_public_id,
        quantity_ordered=order.quantity_ordered,
        total_price=order.total_price,
        delivery_address=order.delivery_address,
        contact_phone=order.contact_phone,
        delivery_notes=order.delivery_notes,
        status=order.status,
        estimated_delivery_date=order.estimated_delivery_date,
        created_at=order.created_at,
        updated_at=order.updated_at,
        product_name=product.name,
        farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
        farmer_name=farmer_profile.full_name if farmer_profile else "Farmer",
        product_images=public_images(product),
        customer_name=f"{consumer_profile.first_name} {consumer_profile.last_name}" if consumer_profile else "Customer",
        # Fall back to the account's phone since orders rarely carry their own contact number
        customer_phone=order.contact_phone or (consumer.phone_number if consumer else None),
    )


GONE_DETAIL = "Orders are placed through checkout and paid with Paystack: POST /api/v1/payments/checkout"

# Ordering without paying is no longer possible; checkout creates the orders
@router.post("", status_code=status.HTTP_410_GONE, include_in_schema=False)
@router.post("/", status_code=status.HTTP_410_GONE, include_in_schema=False)
async def create_order():
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=GONE_DETAIL)

# Also served without the trailing slash: Vercel's /api/v1/:path* rewrite drops
# "/orders/"-style URLs, and the slash redirect points at the backend host (CORS-blocked)
@router.get("", response_model=List[OrderDetailResponse], include_in_schema=False)
@router.get("/", response_model=List[OrderDetailResponse])
async def get_my_orders(
    status: Optional[str] = Query(None, description="Filter by order status"),
    search: Optional[str] = Query(None, description="Search by order number, product name, or farm name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all orders for the current user with optional filtering"""
    service = OrderService(db)
    
    # Create filter object
    order_filter = None
    if status or search:
        order_filter = OrderFilter(status=status, search=search)
    
    orders = service.get_user_orders(current_user.id, order_filter)
    
    # Transform to response format
    order_responses = []
    for order in orders:
        product = order.product
        farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
        
        # Parse images
        product_images = public_images(product)
        
        order_response = OrderDetailResponse(
            id=order.id,
            public_id=order.public_id,
            order_number=order.order_number if order.order_number else f"BF{order.id:06d}",  # Ensure never None
            consumer_id=order.consumer_id,
            product_id=order.product_id,
            product_public_id=order.product_public_id,
            quantity_ordered=order.quantity_ordered,
            total_price=order.total_price,
            delivery_address=order.delivery_address,
            contact_phone=getattr(order, 'contact_phone', None),
            delivery_notes=getattr(order, 'delivery_notes', None),
            status=order.status,
            estimated_delivery_date=getattr(order, 'estimated_delivery_date', None),
            created_at=order.created_at,
            updated_at=order.updated_at,
            product_name=product.name,
            farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
            farmer_name=farmer_profile.full_name if farmer_profile else "Farmer",
            product_images=product_images
        )
        
        order_responses.append(order_response)
    
    return order_responses

@router.get("/farmer/orders", response_model=FarmerOrderListResponse)
async def get_farmer_orders(
    status: Optional[OrderStatus] = Query(None, description="Filter by order status"),
    date_from: Optional[date] = Query(None, description="Orders placed on or after this date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Orders placed on or before this date (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search by order number, product name, or customer name"),
    product_id: Optional[str] = Query(None, description="Only orders for this product (its public id)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Orders placed for the current farmer's products, for the farm dashboard."""
    if current_user.category != UserCategory.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers can view farm orders")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be on or before date_to")

    if product_id is not None:
        product_id = resolve_id(db, Product, product_id, "Product")

    service = OrderService(db)
    orders, total = service.get_farmer_orders(
        current_user.id, status, date_from, date_to, search, skip, limit, product_id=product_id
    )

    # Every order here is for the same farm, so look the profile up once
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()

    items = [_farmer_order_response(order, farmer_profile) for order in orders]
    return FarmerOrderListResponse(items=items, total=total, skip=skip, limit=limit)

@router.get("/farmer/orders/{order_id}", response_model=FarmerOrderResponse)
async def get_farmer_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """One order for the current farmer's products, with the buyer's contact details."""
    order_id = resolve_id(db, Order, order_id, "Order")
    if current_user.category != UserCategory.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers can view farm orders")

    order = OrderService(db).get_farmer_order(current_user.id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    return _farmer_order_response(order, farmer_profile)

@router.get("/{order_id}", response_model=OrderWithDetailsResponse)
async def get_order_details(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed information for a specific order including timeline and issues"""
    order_id = resolve_id(db, Order, order_id, "Order")
    service = OrderService(db)
    
    # Get order details
    order = service.get_order_details(order_id, current_user.id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get timeline and issues
    timeline = service.get_order_timeline(order_id, current_user.id)
    issues = service.get_order_issues(order_id, current_user.id)
    
    # Get product and farmer info
    product = order.product
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
    
    # Parse images
    product_images = public_images(product)
    
    # Transform timeline
    timeline_responses = [
        OrderTimelineResponse(
            id=t.id,
            status=t.status,
            title=t.title,
            description=t.description,
            is_completed=t.is_completed,
            completed_at=t.completed_at,
            created_at=t.created_at
        ) for t in timeline
    ]
    
    # Transform issues
    issue_responses = [
        OrderIssueResponse(
            id=i.id,
            issue_description=i.issue_description,
            status=i.status,
            admin_response=i.admin_response,
            created_at=i.created_at,
            updated_at=i.updated_at
        ) for i in issues
    ]
    
    return OrderWithDetailsResponse(
        id=order.id,
        public_id=order.public_id,
        order_number=order.order_number if order.order_number else f"BF{order.id:06d}",
        consumer_id=order.consumer_id,
        product_id=order.product_id,
        product_public_id=order.product_public_id,
        quantity_ordered=order.quantity_ordered,
        total_price=order.total_price,
        delivery_address=order.delivery_address,
        contact_phone=getattr(order, 'contact_phone', None),
        delivery_notes=getattr(order, 'delivery_notes', None),
        status=order.status,
        estimated_delivery_date=getattr(order, 'estimated_delivery_date', None),
        created_at=order.created_at,
        updated_at=order.updated_at,
        product_name=product.name,
        farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
        farmer_name=farmer_profile.full_name if farmer_profile else "Farmer",
        product_images=product_images,
        timeline=timeline_responses,
        issues=issue_responses
    )

@router.post("/{order_id}/report-issue", response_model=OrderIssueResponse)
async def report_delivery_issue(
    order_id: str,
    issue_data: OrderIssueCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Report a delivery issue for an order"""
    order_id = resolve_id(db, Order, order_id, "Order")
    service = OrderService(db)
    
    issue = service.report_delivery_issue(order_id, current_user.id, issue_data)
    if not issue:
        raise HTTPException(
            status_code=404, 
            detail="Order not found or you don't have permission to report issues for this order"
        )

    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        NotificationService(db).notify_delivery_issue(order, background_tasks)

    return OrderIssueResponse(
        id=issue.id,
        issue_description=issue.issue_description,
        status=issue.status,
        admin_response=issue.admin_response,
        created_at=issue.created_at,
        updated_at=issue.updated_at
    )

@router.post("/{order_id}/confirm-delivery", response_model=OrderDetailResponse)
async def confirm_delivery(
    order_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Confirm that you have received your order"""
    order_id = resolve_id(db, Order, order_id, "Order")
    service = OrderService(db)
    
    order = service.confirm_delivery(order_id, current_user.id)
    if not order:
        raise HTTPException(
            status_code=404, 
            detail="Order not found, already confirmed, or you don't have permission to confirm this order"
        )

    NotificationService(db).notify_delivery_confirmed(order, background_tasks)

    # Get additional details for response
    product = order.product
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
    product_images = public_images(product)
    
    return OrderDetailResponse(
        id=order.id,
        public_id=order.public_id,
        order_number=order.order_number if order.order_number else f"BF{order.id:06d}",
        consumer_id=order.consumer_id,
        product_id=order.product_id,
        product_public_id=order.product_public_id,
        quantity_ordered=order.quantity_ordered,
        total_price=order.total_price,
        delivery_address=order.delivery_address,
        contact_phone=getattr(order, 'contact_phone', None),
        delivery_notes=getattr(order, 'delivery_notes', None),
        status=order.status,
        estimated_delivery_date=getattr(order, 'estimated_delivery_date', None),
        created_at=order.created_at,
        updated_at=order.updated_at,
        product_name=product.name,
        farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
        farmer_name=farmer_profile.full_name if farmer_profile else "Farmer",
        product_images=product_images
    )

@router.get("/{order_id}/timeline", response_model=List[OrderTimelineResponse])
async def get_order_timeline(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get the timeline for a specific order"""
    order_id = resolve_id(db, Order, order_id, "Order")
    service = OrderService(db)
    
    timeline = service.get_order_timeline(order_id, current_user.id)
    
    return [
        OrderTimelineResponse(
            id=t.id,
            status=t.status,
            title=t.title,
            description=t.description,
            is_completed=t.is_completed,
            completed_at=t.completed_at,
            created_at=t.created_at
        ) for t in timeline
    ]

@router.get("/{order_id}/issues", response_model=List[OrderIssueResponse])
async def get_order_issues(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all issues reported for a specific order"""
    order_id = resolve_id(db, Order, order_id, "Order")
    service = OrderService(db)
    
    issues = service.get_order_issues(order_id, current_user.id)
    
    return [
        OrderIssueResponse(
            id=i.id,
            issue_description=i.issue_description,
            status=i.status,
            admin_response=i.admin_response,
            created_at=i.created_at,
            updated_at=i.updated_at
        ) for i in issues
    ]

@router.get("/statistics/summary")
async def get_order_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get order statistics for the current user"""
    service = OrderService(db)
    
    stats = service.get_order_statistics(current_user.id)
    
    return {
        "message": "Order statistics retrieved successfully",
        "data": stats
    }

# Admin/Farmer routes (for managing orders)
@router.put("/{order_id}/status", response_model=OrderDetailResponse)
async def update_order_status(
    order_id: str,
    status_update: OrderStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update order status (for farmers/admin)"""
    order_id = resolve_id(db, Order, order_id, "Order")
    if current_user.category not in ["farmer", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only farmers and administrators can update order status"
        )

    service = OrderService(db)

    # Farmers may only update orders for their own products
    farmer_id = current_user.id if current_user.category == "farmer" else None
    try:
        order = service.update_order_status(order_id, status_update, farmer_id=farmer_id)
    except InvalidStatusTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    NotificationService(db).notify_order_status_changed(order, background_tasks)
    
    # Get additional details for response
    product = order.product
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
    product_images = public_images(product)
    
    return OrderDetailResponse(
        id=order.id,
        public_id=order.public_id,
        order_number=order.order_number if order.order_number else f"BF{order.id:06d}",
        consumer_id=order.consumer_id,
        product_id=order.product_id,
        product_public_id=order.product_public_id,
        quantity_ordered=order.quantity_ordered,
        total_price=order.total_price,
        delivery_address=order.delivery_address,
        contact_phone=getattr(order, 'contact_phone', None),
        delivery_notes=getattr(order, 'delivery_notes', None),
        status=order.status,
        estimated_delivery_date=getattr(order, 'estimated_delivery_date', None),
        created_at=order.created_at,
        updated_at=order.updated_at,
        product_name=product.name,
        farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
        farmer_name=farmer_profile.full_name if farmer_profile else "Farmer",
        product_images=product_images
    )
