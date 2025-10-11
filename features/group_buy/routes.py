from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database import get_db
from core.dependencies import get_current_active_user
from features.auth.models import User
from features.marketplace.models import Product, AvailabilityStatus
from features.group_buy.service import GroupBuyService
from features.group_buy.chat_service import ChatService, connection_manager
from features.group_buy.schemas import (
    GroupBuyCreate, GroupBuyUpdate, GroupBuyResponse, GroupBuyDetailResponse,
    GroupMemberJoin, GroupMemberResponse, GroupTransactionCreate, GroupTransactionResponse,
    GroupProgressResponse, GroupInviteRequest, GroupInviteResponse,
    GroupNotificationResponse, StockAlertRequest, StockAlertResponse,
    GroupDiscoveryRequest, GroupPublicResponse, GroupJoinRequest, GroupJoinResponse,
    GroupPricingRequest, GroupPricingResponse, GroupJoinValidationResponse,
    # Chat schemas
    ChatMessageSend, ChatMessageResponse, MessageHistoryRequest, MessageHistoryResponse,
    ChatMembershipResponse, ChatReportCreate, ChatModerationAction, ChatStatsResponse,
    WebSocketMessage, WebSocketMessageType, TypingIndicator
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/products/available", response_model=List[dict])
async def get_available_products_for_group_buy(
    db: Session = Depends(get_db)
):
    """Get available products for group buy creation"""
    try:
        products = db.query(Product).filter(
            Product.availability == AvailabilityStatus.IN_STOCK,
            Product.is_listed == True,
            Product.is_approved == True
        ).all()
        
        return [
            {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "category": product.category,
                "location": product.location,
                "quantity": product.quantity
            }
            for product in products
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch products")

@router.post("/groups", response_model=GroupBuyResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupBuyCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new group buy"""
    try:
        service = GroupBuyService(db)
        group = await service.create_group(current_user.id, group_data)
        return group
    except ValueError as e:
        logger.error(f"Validation error creating group: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating group: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create group: {str(e)}")

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
        member = await service.join_group(current_user.id, join_data)
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
        transaction = await service.add_contribution(group_id, current_user.id, amount, payment_method)
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

# ========================
# CHAT ROUTES
# ========================

@router.get("/groups/{group_id}/chat/messages", response_model=MessageHistoryResponse)
async def get_chat_messages(
    group_id: int,
    limit: int = Query(50, ge=1, le=100, description="Number of messages to retrieve"),
    before_message_id: Optional[int] = Query(None, description="Get messages before this message ID"),
    after_message_id: Optional[int] = Query(None, description="Get messages after this message ID"),
    include_deleted: bool = Query(False, description="Include deleted messages"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get chat messages for a group"""
    try:
        # Verify user is a member of the group
        group_service = GroupBuyService(db)
        group_details = group_service.get_group_details(group_id, current_user.id)
        if not group_details["is_member"] and not group_details["is_creator"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        chat_service = ChatService(db)
        
        # Get or create chat for the group
        chat = None
        if hasattr(group_details["group"], "chat") and group_details["group"]["chat"]:
            chat_id = group_details["group"]["chat"]["id"]
        else:
            # Create chat if it doesn't exist
            chat = await chat_service.create_group_chat(group_id)
            await chat_service.add_member_to_chat(chat.id, current_user.id)
            chat_id = chat.id
        
        request = MessageHistoryRequest(
            limit=limit,
            before_message_id=before_message_id,
            after_message_id=after_message_id,
            include_deleted=include_deleted
        )
        
        messages = chat_service.get_chat_messages(chat_id, current_user.id, request)
        return messages
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching chat messages for group {group_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch chat messages")

@router.post("/groups/{group_id}/chat/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    group_id: int,
    message_data: ChatMessageSend,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Send a message to group chat"""
    try:
        # Validate message content
        if not message_data.message_content or len(message_data.message_content.strip()) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content cannot be empty")
        
        if len(message_data.message_content) > 2000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content too long (max 2000 characters)")
        
        # Verify user is a member of the group
        group_service = GroupBuyService(db)
        group_details = group_service.get_group_details(group_id, current_user.id)
        if not group_details["is_member"] and not group_details["is_creator"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        chat_service = ChatService(db)
        
        # Get or create chat
        chat = None
        if hasattr(group_details["group"], "chat") and group_details["group"]["chat"]:
            chat_id = group_details["group"]["chat"]["id"]
        else:
            # Create chat if it doesn't exist
            chat = await chat_service.create_group_chat(group_id)
            await chat_service.add_member_to_chat(chat.id, current_user.id)
            chat_id = chat.id
        
        message = await chat_service.send_message(chat_id, current_user.id, message_data)
        return message
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending message to group {group_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send message")

@router.put("/groups/{group_id}/chat/messages/{message_id}/pin")
async def pin_chat_message(
    group_id: int,
    message_id: int,
    is_pinned: bool = Query(..., description="Whether to pin or unpin the message"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Pin or unpin a chat message (moderators only)"""
    try:
        # Verify user is a group creator (moderator)
        group_service = GroupBuyService(db)
        group_details = group_service.get_group_details(group_id, current_user.id)
        if not group_details["is_creator"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only group creators can pin messages")
        
        chat_service = ChatService(db)
        chat_id = group_details["group"]["chat"]["id"]
        
        message = await chat_service.pin_message(chat_id, message_id, current_user.id, is_pinned)
        return message
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to pin/unpin message")

@router.delete("/groups/{group_id}/chat/messages/{message_id}")
async def delete_chat_message(
    group_id: int,
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a chat message (author or moderator only)"""
    try:
        # Verify user is a member of the group
        group_service = GroupBuyService(db)
        group_details = group_service.get_group_details(group_id, current_user.id)
        if not group_details["is_member"] and not group_details["is_creator"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        # TODO: Implement message deletion logic
        # Check if user is message author or group creator
        
        return {"message": "Message deleted successfully"}
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete message")

@router.get("/groups/{group_id}/chat/stats", response_model=ChatStatsResponse)
async def get_chat_stats(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get chat statistics for a group"""
    try:
        # Verify user is a member of the group
        group_service = GroupBuyService(db)
        group_details = group_service.get_group_details(group_id, current_user.id)
        if not group_details["is_member"] and not group_details["is_creator"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        chat_service = ChatService(db)
        chat_id = group_details["group"]["chat"]["id"]
        
        stats = chat_service.get_chat_stats(chat_id)
        return stats
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch chat stats")

@router.post("/groups/{group_id}/chat/report")
async def report_chat_message(
    group_id: int,
    report_data: ChatReportCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Report a chat message for moderation"""
    try:
        # Verify user is a member of the group
        group_service = GroupBuyService(db)
        group_details = group_service.get_group_details(group_id, current_user.id)
        if not group_details["is_member"] and not group_details["is_creator"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        # TODO: Implement message reporting logic
        
        return {"message": "Message reported successfully"}
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to report message")

@router.websocket("/groups/{group_id}/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    group_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time chat"""
    chat_service = ChatService(db)
    user_id = None  # TODO: Get user from WebSocket authentication
    
    try:
        # TODO: Implement WebSocket authentication
        # For now, we'll need to pass user_id through query params or headers
        
        # Verify user is a member of the group
        # group_service = GroupBuyService(db)
        # group_details = group_service.get_group_details(group_id, user_id)
        # if not group_details["is_member"] and not group_details["is_creator"]:
        #     await websocket.close(code=4003, reason="Access denied")
        #     return
        
        # Get chat ID
        # chat_id = group_details["group"]["chat"]["id"]
        chat_id = group_id  # Temporary - use group_id as chat_id
        
        # Connect to WebSocket
        await connection_manager.connect(websocket, chat_id, user_id or 1)  # Temporary user_id
        
        try:
            while True:
                # Receive message from WebSocket
                data = await websocket.receive_json()
                
                # Handle different message types
                message_type = data.get("type")
                
                if message_type == "message":
                    # Send chat message
                    message_content = data.get("message", "")
                    if message_content:
                        message_data = ChatMessageSend(message_content=message_content)
                        await chat_service.send_message(chat_id, user_id or 1, message_data)
                
                elif message_type == "typing":
                    # Handle typing indicator
                    is_typing = data.get("is_typing", False)
                    await connection_manager.handle_typing(chat_id, user_id or 1, is_typing)
                
                elif message_type == "heartbeat":
                    # Respond to heartbeat
                    await websocket.send_json({"type": "heartbeat", "timestamp": "now"})
                
        except WebSocketDisconnect:
            connection_manager.disconnect(websocket, chat_id)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.send_json({
                "type": "error",
                "message": "An error occurred"
            })
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        try:
            await websocket.close(code=4000, reason="Connection error")
        except:
            pass