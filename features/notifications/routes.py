from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from features.auth.models import User
from features.notifications.schemas import NotificationResponse, UnreadCountResponse
from features.notifications.service import NotificationService
from core.dependencies import get_current_active_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/", response_model=List[NotificationResponse])
async def get_my_notifications(
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List the current user's notifications, newest first."""
    service = NotificationService(db)
    return service.get_user_notifications(current_user.id, unread_only, skip, limit)

@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = NotificationService(db)
    return {"unread_count": service.get_unread_count(current_user.id)}

@router.patch("/read-all")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = NotificationService(db)
    updated = service.mark_all_as_read(current_user.id)
    return {"message": "All notifications marked as read", "updated": updated}

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = NotificationService(db)
    notification = service.mark_as_read(notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification
