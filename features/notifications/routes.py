import asyncio
import time
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db, SessionLocal
from features.auth.models import User
from features.notifications.connection_manager import notification_manager
from features.notifications.schemas import NotificationResponse, UnreadCountResponse
from features.notifications.service import NotificationService
from core.dependencies import get_current_active_user
from core.security import decode_token

logger = logging.getLogger(__name__)

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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = NotificationService(db)
    updated = service.mark_all_as_read(current_user.id)
    service.push_unread_count(current_user.id, background_tasks)
    return {"message": "All notifications marked as read", "updated": updated}

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = NotificationService(db)
    notification = service.mark_as_read(notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    service.push_unread_count(current_user.id, background_tasks)
    return notification

# Close codes in the 4000-4999 range are application-defined
WS_UNAUTHORIZED = 4001
WS_TOKEN_EXPIRED = 4002

def _authenticate_ws_token(token: str) -> Optional[tuple]:
    """Validate an access token the same way get_current_user does; returns (user_id, exp)."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = int(payload.get("sub"))
    except Exception:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or not user.is_active:
            return None
        return user_id, payload.get("exp")
    finally:
        db.close()

@router.websocket("/ws")
async def notifications_websocket(websocket: WebSocket, token: str = Query(...)):
    """Real-time notifications. Browsers can't set headers on a WebSocket, so the
    access token goes in the query string: /api/v1/notifications/ws?token=<access_token>

    Server -> client messages:
      {"type": "unread_count", "data": {"unread_count": 3}}   on connect and whenever it changes
      {"type": "notification", "data": {...NotificationResponse}}   when a new one is created
      {"type": "pong"}   in reply to a client "ping"

    The socket is closed with code 4002 when the access token expires; reconnect with a fresh one.
    """
    await websocket.accept()

    auth = _authenticate_ws_token(token)
    if not auth:
        await websocket.close(code=WS_UNAUTHORIZED, reason="Could not validate credentials")
        return
    user_id, exp = auth

    notification_manager.connect(websocket, user_id)
    try:
        # Don't hold a DB session open for the life of the socket
        db = SessionLocal()
        try:
            unread_count = NotificationService(db).get_unread_count(user_id)
        finally:
            db.close()
        await websocket.send_json({"type": "unread_count", "data": {"unread_count": unread_count}})

        while True:
            remaining = exp - time.time() if exp else None
            if remaining is not None and remaining <= 0:
                await websocket.close(code=WS_TOKEN_EXPIRED, reason="Token expired")
                return
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=remaining)
            except asyncio.TimeoutError:
                continue  # Loop back round to the expiry check
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Notifications socket error for user %s", user_id)
    finally:
        notification_manager.disconnect(websocket, user_id)
