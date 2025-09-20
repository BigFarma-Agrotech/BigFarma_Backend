from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from core.dependencies import get_current_active_user
from features.auth.models import User
from features.group_buy.service import GroupBuyService
from features.group_buy.schemas import (
    GroupBuyCreate, GroupBuyUpdate, GroupBuyResponse, GroupBuyDetailResponse,
    GroupMemberJoin, GroupMemberResponse, GroupTransactionCreate, GroupTransactionResponse,
    GroupProgressResponse, GroupInviteRequest, GroupInviteResponse,
    GroupNotificationResponse, StockAlertRequest, StockAlertResponse,
    GroupDiscoveryRequest, GroupPublicResponse, GroupJoinRequest, GroupJoinResponse,
    GroupPricingRequest, GroupPricingResponse, GroupJoinValidationResponse
)

router = APIRouter()

@router.post("/groups", response_model=GroupBuyResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupBuyCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new group buy"""
    try:
        service = GroupBuyService(db)
        group = service.create_group(current_user.id, group_data)
        return group
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create group")

@router.get("/groups", response_model=List[GroupBuyResponse])
async def get_user_groups(
    status: Optional[str] = Query(None, description="Filter by group status"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all groups for the current user"""
    try:
        service = GroupBuyService(db)
        groups = service.get_user_groups(current_user.id, status)
        return groups
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch groups")

@router.get("/groups/{group_id}", response_model=GroupBuyDetailResponse)
async def get_group_details(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific group"""
    try:
        service = GroupBuyService(db)
        group_details = service.get_group_details(group_id, current_user.id)
        return group_details
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch group details")

@router.put("/groups/{group_id}", response_model=GroupBuyResponse)
async def update_group(
    group_id: int,
    update_data: GroupBuyUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a group (only creator can update)"""
    try:
        service = GroupBuyService(db)
        group = service.update_group(group_id, current_user.id, update_data)
        return group
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update group")

@router.get("/groups/{group_id}/progress", response_model=GroupProgressResponse)
async def get_group_progress(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get progress information for a group"""
    try:
        service = GroupBuyService(db)
        progress = service.get_group_progress(group_id)
        return progress
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch group progress")

@router.post("/groups/{group_id}/join", response_model=GroupMemberResponse, status_code=status.HTTP_201_CREATED)
async def join_group(
    group_id: int,
    join_data: GroupMemberJoin,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Join an existing group"""
    try:
        service = GroupBuyService(db)
        member = service.join_group(current_user.id, join_data)
        return member
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to join group")

@router.post("/groups/{group_id}/leave", status_code=status.HTTP_200_OK)
async def leave_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Leave a group"""
    try:
        service = GroupBuyService(db)
        success = service.leave_group(group_id, current_user.id)
        return {"message": "Successfully left the group", "success": success}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to leave group")

@router.post("/groups/{group_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cancel a group (only creator can cancel)"""
    try:
        service = GroupBuyService(db)
        success = service.cancel_group(group_id, current_user.id)
        return {"message": "Group cancelled successfully", "success": success}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cancel group")

@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a group permanently (only creator can delete, only empty or cancelled groups)"""
    try:
        service = GroupBuyService(db)
        success = service.delete_group(group_id, current_user.id)
        return {"message": "Group deleted successfully", "success": success}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete group")

@router.post("/groups/{group_id}/contribute", response_model=GroupTransactionResponse, status_code=status.HTTP_201_CREATED)
async def add_contribution(
    group_id: int,
    amount: float = Query(..., gt=0, description="Contribution amount"),
    payment_method: str = Query("wallet", description="Payment method"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a contribution to the group wallet"""
    try:
        service = GroupBuyService(db)
        transaction = service.add_contribution(group_id, current_user.id, amount, payment_method)
        return transaction
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add contribution")

@router.get("/groups/{group_id}/share", response_model=GroupInviteResponse)
async def get_shareable_link(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the shareable link for a group"""
    try:
        service = GroupBuyService(db)
        group_details = service.get_group_details(group_id, current_user.id)
        
        # Check if user is creator or member
        if not group_details["is_creator"] and not group_details["is_member"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        return GroupInviteResponse(
            invitation_link=group_details["group"]["shareable_link"],
            invitation_token="",  # Could implement token-based invitations
            expires_at=None  # Could implement expiration
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get shareable link")

@router.post("/groups/{group_id}/invite", response_model=GroupInviteResponse)
async def invite_to_group(
    group_id: int,
    invite_data: GroupInviteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Invite someone to join a group"""
    try:
        service = GroupBuyService(db)
        group_details = service.get_group_details(group_id, current_user.id)
        
        # Check if user is creator or member
        if not group_details["is_creator"] and not group_details["is_member"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        # TODO: Implement actual invitation logic
        # This could involve:
        # 1. Sending email/SMS invitations
        # 2. Creating invitation tokens
        # 3. Tracking invitation status
        
        return GroupInviteResponse(
            invitation_link=group_details["group"]["shareable_link"],
            invitation_token="",  # Generate unique token
            expires_at=None  # Set expiration date
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send invitation")

@router.get("/groups/{group_id}/notifications", response_model=List[GroupNotificationResponse])
async def get_group_notifications(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get notifications for a group"""
    try:
        service = GroupBuyService(db)
        group_details = service.get_group_details(group_id, current_user.id)
        
        # Check if user is creator or member
        if not group_details["is_creator"] and not group_details["is_member"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        # TODO: Implement notification fetching
        # This would query the GroupNotification table
        notifications = []  # Placeholder
        
        return notifications
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch notifications")

@router.post("/groups/{group_id}/stock-alert", response_model=StockAlertResponse)
async def create_stock_alert(
    group_id: int,
    alert_data: StockAlertRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a stock alert for a group"""
    try:
        service = GroupBuyService(db)
        group_details = service.get_group_details(group_id, current_user.id)
        
        # Check if user is creator or member
        if not group_details["is_creator"] and not group_details["is_member"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        # TODO: Implement stock alert logic
        # This would involve:
        # 1. Monitoring product stock levels
        # 2. Sending alerts when stock is low
        # 3. Suggesting alternative products
        
        return StockAlertResponse(
            group_id=group_id,
            alert_type=alert_data.alert_type,
            message=alert_data.message,
            suggested_alternatives=[],  # TODO: Implement alternative suggestions
            created_at=None  # TODO: Set current timestamp
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create stock alert")

@router.get("/groups/public/{shareable_link}")
async def join_group_by_link(
    shareable_link: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Join a group using a shareable link"""
    try:
        # TODO: Implement link-based joining
        # This would involve:
        # 1. Finding group by shareable link
        # 2. Showing group details
        # 3. Allowing user to join
        
        return {"message": "Group found", "shareable_link": shareable_link}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process shareable link")

@router.get("/groups/{group_id}/analytics")
async def get_group_analytics(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get analytics for a group (creator only)"""
    try:
        service = GroupBuyService(db)
        group_details = service.get_group_details(group_id, current_user.id)
        
        # Check if user is creator
        if not group_details["is_creator"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only group creator can view analytics")
        
        # TODO: Implement analytics
        # This could include:
        # 1. Member engagement metrics
        # 2. Contribution patterns
        # 3. Progress over time
        # 4. Success rate predictions
        
        return {"message": "Analytics not implemented yet"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch analytics")

# Group Discovery and Public Access Routes
@router.get("/groups/public", response_model=List[GroupPublicResponse])
async def get_public_groups(
    location: Optional[str] = Query(None, description="Filter by location"),
    product_name: Optional[str] = Query(None, description="Search by product name"),
    category: Optional[str] = Query(None, description="Filter by product category"),
    min_price: Optional[float] = Query(None, gt=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, gt=0, description="Maximum price filter"),
    sort_by: Optional[str] = Query("newest", description="Sort by: newest, oldest, price_asc, price_desc, progress"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    db: Session = Depends(get_db)
):
    """Get public groups for discovery and browsing"""
    try:
        service = GroupBuyService(db)
        discovery_request = GroupDiscoveryRequest(
            location=location,
            product_name=product_name,
            category=category,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by
        )
        groups = service.get_public_groups(discovery_request, skip, limit)
        return groups
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch public groups")

@router.get("/groups/public/{group_id}")
async def get_public_group_details(
    group_id: int,
    db: Session = Depends(get_db)
):
    """Get public group details for non-members"""
    try:
        service = GroupBuyService(db)
        group_details = service.get_public_group_details(group_id)
        return group_details
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch group details")

@router.get("/groups/{group_id}/validate-join", response_model=GroupJoinValidationResponse)
async def validate_group_join(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Validate if a user can join a group"""
    try:
        service = GroupBuyService(db)
        validation = service.validate_group_join(group_id, current_user.id)
        return validation
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to validate group join")

@router.post("/groups/{group_id}/pricing", response_model=GroupPricingResponse)
async def calculate_group_pricing(
    group_id: int,
    quantity: float = Query(..., gt=0, description="Quantity to calculate price for"),
    db: Session = Depends(get_db)
):
    """Calculate pricing for a specific quantity in a group"""
    try:
        service = GroupBuyService(db)
        pricing = service.calculate_group_pricing(group_id, quantity)
        return pricing
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to calculate pricing")

@router.post("/groups/{group_id}/join-public", response_model=GroupJoinResponse, status_code=status.HTTP_201_CREATED)
async def join_public_group(
    group_id: int,
    join_request: GroupJoinRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Join a public group (with payment placeholder)"""
    try:
        service = GroupBuyService(db)
        join_response = service.request_group_join(current_user.id, join_request)
        return join_response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to join group")