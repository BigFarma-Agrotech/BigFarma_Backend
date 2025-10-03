from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from features.orders.schemas import (
    OrderDetailResponse, OrderWithDetailsResponse, OrderTimelineResponse, 
    OrderIssueResponse, OrderIssueCreate, OrderStatusUpdate, OrderFilter
)
from features.marketplace.schemas import OrderCreate
from features.orders.service import OrderService
from features.marketplace.models import Order, Product
from features.users.models import FarmerProfile
from features.auth.models import User
from core.dependencies import get_current_active_user

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new order for the current consumer."""
    if current_user.category != "consumer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only consumers can create orders")

    service = OrderService(db)
    order = service.create_order(current_user.id, order_data)
    if not order:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product unavailable or order could not be created")

    product = order.product
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first() if product else None
    product_images = product.images.split(',') if product and product.images else []

    return OrderDetailResponse(
        id=order.id,
        order_number=order.order_number if order.order_number else f"BF{order.id:06d}",
        consumer_id=order.consumer_id,
        product_id=order.product_id,
        quantity_ordered=order.quantity_ordered,
        total_price=order.total_price,
        delivery_address=order.delivery_address,
        contact_phone=getattr(order, 'contact_phone', None),
        delivery_notes=getattr(order, 'delivery_notes', None),
        status=order.status,
        estimated_delivery_date=getattr(order, 'estimated_delivery_date', None),
        created_at=order.created_at,
        updated_at=order.updated_at,
        product_name=product.name if product else "Unknown Product",
        farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
        farmer_name=farmer_profile.full_name if farmer_profile else "Farmer",
        product_images=product_images,
    )

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
        product_images = product.images.split(',') if product.images else []
        
        order_response = OrderDetailResponse(
            id=order.id,
            order_number=order.order_number if order.order_number else f"BF{order.id:06d}",  # Ensure never None
            consumer_id=order.consumer_id,
            product_id=order.product_id,
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

@router.get("/{order_id}", response_model=OrderWithDetailsResponse)
async def get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed information for a specific order including timeline and issues"""
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
    product_images = product.images.split(',') if product.images else []
    
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
        order_number=order.order_number if order.order_number else f"BF{order.id:06d}",
        consumer_id=order.consumer_id,
        product_id=order.product_id,
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
    order_id: int,
    issue_data: OrderIssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Report a delivery issue for an order"""
    service = OrderService(db)
    
    issue = service.report_delivery_issue(order_id, current_user.id, issue_data)
    if not issue:
        raise HTTPException(
            status_code=404, 
            detail="Order not found or you don't have permission to report issues for this order"
        )
    
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
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Confirm that you have received your order"""
    service = OrderService(db)
    
    order = service.confirm_delivery(order_id, current_user.id)
    if not order:
        raise HTTPException(
            status_code=404, 
            detail="Order not found, already confirmed, or you don't have permission to confirm this order"
        )
    
    # Get additional details for response
    product = order.product
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
    product_images = product.images.split(',') if product.images else []
    
    return OrderDetailResponse(
        id=order.id,
        order_number=order.order_number if order.order_number else f"BF{order.id:06d}",
        consumer_id=order.consumer_id,
        product_id=order.product_id,
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
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get the timeline for a specific order"""
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
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all issues reported for a specific order"""
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
    order_id: int,
    status_update: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update order status (for farmers/admin)"""
    # TODO: Add proper authorization check for farmers
    if current_user.category not in ["farmer", "admin"]:
        raise HTTPException(
            status_code=403, 
            detail="Only farmers and administrators can update order status"
        )
    
    service = OrderService(db)
    
    order = service.update_order_status(order_id, status_update)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get additional details for response
    product = order.product
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
    product_images = product.images.split(',') if product.images else []
    
    return OrderDetailResponse(
        id=order.id,
        order_number=order.order_number if order.order_number else f"BF{order.id:06d}",
        consumer_id=order.consumer_id,
        product_id=order.product_id,
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
