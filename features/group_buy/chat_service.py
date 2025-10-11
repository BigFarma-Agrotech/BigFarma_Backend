import logging
import asyncio
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from fastapi import WebSocket, WebSocketDisconnect

from features.group_buy.models import (
    GroupBuy, GroupChat, ChatMessage, ChatMembership, ChatReport, 
    MessageType, GroupStatus, GroupMemberStatus
)
from features.group_buy.schemas import (
    GroupChatCreate, ChatMessageCreate, ChatMessageSend, ChatMessageResponse,
    ChatMembershipCreate, WebSocketMessage, WebSocketMessageType, TypingIndicator,
    MessageHistoryRequest, MessageHistoryResponse, ChatReportCreate,
    ChatModerationAction, ChatStatsResponse
)
from features.auth.models import User

logger = logging.getLogger(__name__)

class WebSocketConnectionManager:
    """Manage WebSocket connections for real-time chat"""
    
    def __init__(self):
        # chat_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # websocket -> user_id mapping
        self.connection_users: Dict[WebSocket, int] = {}
        # user_id -> set of typing indicators
        self.typing_users: Dict[int, Set[int]] = {}
    
    async def connect(self, websocket: WebSocket, chat_id: int, user_id: int):
        """Accept WebSocket connection and add to chat room"""
        await websocket.accept()
        
        if chat_id not in self.active_connections:
            self.active_connections[chat_id] = set()
        
        self.active_connections[chat_id].add(websocket)
        self.connection_users[websocket] = user_id
        
        logger.info(f"User {user_id} connected to chat {chat_id}")
        
        # Notify other users that someone joined
        await self.broadcast_to_chat(chat_id, {
            "type": WebSocketMessageType.USER_JOINED,
            "data": {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }, exclude_websocket=websocket)
    
    def disconnect(self, websocket: WebSocket, chat_id: int):
        """Remove WebSocket connection"""
        if chat_id in self.active_connections:
            self.active_connections[chat_id].discard(websocket)
            if not self.active_connections[chat_id]:
                del self.active_connections[chat_id]
        
        user_id = self.connection_users.pop(websocket, None)
        if user_id:
            logger.info(f"User {user_id} disconnected from chat {chat_id}")
            
            # Remove from typing users
            if chat_id in self.typing_users:
                self.typing_users[chat_id].discard(user_id)
            
            # Notify other users that someone left
            asyncio.create_task(self.broadcast_to_chat(chat_id, {
                "type": WebSocketMessageType.USER_LEFT,
                "data": {
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }))
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast_to_chat(self, chat_id: int, message: dict, exclude_websocket: WebSocket = None):
        """Broadcast message to all connections in a chat"""
        if chat_id not in self.active_connections:
            return
        
        connections_copy = self.active_connections[chat_id].copy()
        for websocket in connections_copy:
            if websocket != exclude_websocket:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to websocket: {e}")
                    # Remove broken connection
                    self.active_connections[chat_id].discard(websocket)
                    self.connection_users.pop(websocket, None)
    
    async def handle_typing(self, chat_id: int, user_id: int, is_typing: bool):
        """Handle typing indicators"""
        if chat_id not in self.typing_users:
            self.typing_users[chat_id] = set()
        
        if is_typing:
            self.typing_users[chat_id].add(user_id)
        else:
            self.typing_users[chat_id].discard(user_id)
        
        # Broadcast typing status
        await self.broadcast_to_chat(chat_id, {
            "type": WebSocketMessageType.TYPING,
            "data": {
                "user_id": user_id,
                "is_typing": is_typing,
                "typing_users": list(self.typing_users[chat_id])
            }
        })
    
    def get_active_users(self, chat_id: int) -> List[int]:
        """Get list of active user IDs in a chat"""
        if chat_id not in self.active_connections:
            return []
        
        active_users = []
        for websocket in self.active_connections[chat_id]:
            user_id = self.connection_users.get(websocket)
            if user_id:
                active_users.append(user_id)
        
        return list(set(active_users))  # Remove duplicates

# Global connection manager instance
connection_manager = WebSocketConnectionManager()

class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.connection_manager = connection_manager
    
    async def create_group_chat(self, group_id: int) -> GroupChat:
        """Create a new chat for a group"""
        try:
            # Check if group exists
            group = self.db.query(GroupBuy).filter(GroupBuy.id == group_id).first()
            if not group:
                raise ValueError("Group not found")
            
            # Check if chat already exists
            existing_chat = self.db.query(GroupChat).filter(GroupChat.group_id == group_id).first()
            if existing_chat:
                return existing_chat
            
            # Create new chat
            chat = GroupChat(
                group_id=group_id,
                is_active=True,
                is_read_only=False,
                allow_member_invite=True,
                auto_close_on_completion=True
            )
            
            self.db.add(chat)
            self.db.flush()
            
            # Add group creator as first member and moderator
            creator_membership = ChatMembership(
                chat_id=chat.id,
                user_id=group.creator_id,
                is_active=True,
                is_moderator=True,
                notify_on_mention=True,
                notify_on_all_messages=True
            )
            
            self.db.add(creator_membership)
            
            # Send welcome system message
            welcome_message = ChatMessage(
                chat_id=chat.id,
                user_id=None,  # System message
                message_content=f"Welcome to the group chat for '{group.group_name}'! 🎉",
                message_type=MessageType.SYSTEM
            )
            
            self.db.add(welcome_message)
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"Created chat {chat.id} for group {group_id}")
            return chat
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating group chat: {str(e)}")
            raise
    
    async def add_member_to_chat(self, chat_id: int, user_id: int, is_moderator: bool = False) -> ChatMembership:
        """Add a user to a chat"""
        try:
            # Check if chat exists
            chat = self.db.query(GroupChat).filter(GroupChat.id == chat_id).first()
            if not chat:
                raise ValueError("Chat not found")
            
            # Check if user is already a member
            existing_membership = self.db.query(ChatMembership).filter(
                ChatMembership.chat_id == chat_id,
                ChatMembership.user_id == user_id,
                ChatMembership.is_active == True
            ).first()
            
            if existing_membership:
                return existing_membership
            
            # Create membership
            membership = ChatMembership(
                chat_id=chat_id,
                user_id=user_id,
                is_active=True,
                is_moderator=is_moderator,
                notify_on_mention=True,
                notify_on_all_messages=True
            )
            
            self.db.add(membership)
            self.db.commit()
            self.db.refresh(membership)
            
            # Send system message about new member
            user = self.db.query(User).filter(User.id == user_id).first()
            user_name = user.email or user.phone_number if user else f"User {user_id}"
            
            await self.send_system_message(
                chat_id=chat_id,
                message=f"{user_name} joined the group! 👋",
                message_type=MessageType.JOIN_NOTIFICATION
            )
            
            logger.info(f"Added user {user_id} to chat {chat_id}")
            return membership
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding member to chat: {str(e)}")
            raise
    
    async def send_message(self, chat_id: int, user_id: int, message_data: ChatMessageSend) -> ChatMessageResponse:
        """Send a message to a chat"""
        try:
            # Verify user is a member of the chat
            membership = self.db.query(ChatMembership).filter(
                ChatMembership.chat_id == chat_id,
                ChatMembership.user_id == user_id,
                ChatMembership.is_active == True
            ).first()
            
            if not membership:
                raise ValueError("User is not a member of this chat")
            
            # Check if chat is read-only
            chat = self.db.query(GroupChat).filter(GroupChat.id == chat_id).first()
            if chat.is_read_only:
                raise ValueError("Chat is read-only")
            
            # Validate reply-to message if specified
            reply_to_message = None
            if message_data.reply_to_message_id:
                reply_to_message = self.db.query(ChatMessage).filter(
                    ChatMessage.id == message_data.reply_to_message_id,
                    ChatMessage.chat_id == chat_id,
                    ChatMessage.is_deleted == False
                ).first()
                
                if not reply_to_message:
                    raise ValueError("Reply-to message not found")
            
            # Create message
            message = ChatMessage(
                chat_id=chat_id,
                user_id=user_id,
                message_content=message_data.message_content,
                message_type=MessageType.TEXT,
                reply_to_message_id=message_data.reply_to_message_id
            )
            
            self.db.add(message)
            
            # Update thread count if this is a reply
            if reply_to_message:
                reply_to_message.thread_count += 1
            
            # Update chat's last message timestamp
            chat.last_message_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(message)
            
            # Create response object
            user = self.db.query(User).filter(User.id == user_id).first()
            response = ChatMessageResponse(
                id=message.id,
                chat_id=message.chat_id,
                user_id=message.user_id,
                message_content=message.message_content,
                message_type=message.message_type,
                is_pinned=message.is_pinned,
                is_deleted=message.is_deleted,
                is_edited=message.is_edited,
                pin_order=message.pin_order,
                thread_count=message.thread_count,
                created_at=message.created_at,
                edited_at=message.edited_at,
                pinned_at=message.pinned_at,
                pinned_by_user_id=message.pinned_by_user_id,
                user_name=user.email or user.phone_number if user else None,
                user_email=user.email if user else None,
                reply_to=self._format_reply_message(reply_to_message) if reply_to_message else None
            )
            
            # Broadcast message to all connected users
            await self.connection_manager.broadcast_to_chat(chat_id, {
                "type": WebSocketMessageType.MESSAGE,
                "data": response.dict(),
                "user_id": user_id,
                "chat_id": chat_id
            })
            
            # Update unread counts for other members
            self._update_unread_counts(chat_id, message.id, exclude_user_id=user_id)
            
            logger.info(f"Message sent to chat {chat_id} by user {user_id}")
            return response
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error sending message: {str(e)}")
            raise
    
    async def send_system_message(self, chat_id: int, message: str, message_type: MessageType = MessageType.SYSTEM) -> ChatMessage:
        """Send a system message to a chat"""
        try:
            system_message = ChatMessage(
                chat_id=chat_id,
                user_id=None,  # System message
                message_content=message,
                message_type=message_type
            )
            
            self.db.add(system_message)
            
            # Update chat's last message timestamp
            chat = self.db.query(GroupChat).filter(GroupChat.id == chat_id).first()
            if chat:
                chat.last_message_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(system_message)
            
            # Broadcast system message
            response = ChatMessageResponse(
                id=system_message.id,
                chat_id=system_message.chat_id,
                user_id=None,
                message_content=system_message.message_content,
                message_type=system_message.message_type,
                is_pinned=False,
                is_deleted=False,
                is_edited=False,
                pin_order=None,
                thread_count=0,
                created_at=system_message.created_at,
                edited_at=None,
                pinned_at=None,
                pinned_by_user_id=None,
                user_name="System",
                user_email=None
            )
            
            await self.connection_manager.broadcast_to_chat(chat_id, {
                "type": WebSocketMessageType.MESSAGE,
                "data": response.dict(),
                "chat_id": chat_id
            })
            
            return system_message
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error sending system message: {str(e)}")
            raise
    
    def get_chat_messages(self, chat_id: int, user_id: int, request: MessageHistoryRequest) -> MessageHistoryResponse:
        """Get chat message history with pagination"""
        try:
            # Verify user has access to chat
            membership = self.db.query(ChatMembership).filter(
                ChatMembership.chat_id == chat_id,
                ChatMembership.user_id == user_id,
                ChatMembership.is_active == True
            ).first()
            
            if not membership:
                raise ValueError("User is not a member of this chat")
            
            # Build query
            query = self.db.query(ChatMessage).filter(
                ChatMessage.chat_id == chat_id
            )
            
            if not request.include_deleted:
                query = query.filter(ChatMessage.is_deleted == False)
            
            if request.message_type:
                query = query.filter(ChatMessage.message_type == request.message_type)
            
            if request.before_message_id:
                query = query.filter(ChatMessage.id < request.before_message_id)
            
            if request.after_message_id:
                query = query.filter(ChatMessage.id > request.after_message_id)
            
            # Order by creation time (newest first for pagination)
            query = query.order_by(desc(ChatMessage.created_at))
            
            # Get total count
            total_count = query.count()
            
            # Apply limit
            messages = query.limit(request.limit + 1).all()  # +1 to check if there are more
            
            has_more = len(messages) > request.limit
            if has_more:
                messages = messages[:-1]  # Remove the extra message
            
            # Format messages
            formatted_messages = []
            for message in messages:
                user = self.db.query(User).filter(User.id == message.user_id).first() if message.user_id else None
                reply_to_message = None
                
                if message.reply_to_message_id:
                    reply_to_message = self.db.query(ChatMessage).filter(
                        ChatMessage.id == message.reply_to_message_id
                    ).first()
                
                formatted_message = ChatMessageResponse(
                    id=message.id,
                    chat_id=message.chat_id,
                    user_id=message.user_id,
                    message_content=message.message_content,
                    message_type=message.message_type,
                    is_pinned=message.is_pinned,
                    is_deleted=message.is_deleted,
                    is_edited=message.is_edited,
                    pin_order=message.pin_order,
                    thread_count=message.thread_count,
                    created_at=message.created_at,
                    edited_at=message.edited_at,
                    pinned_at=message.pinned_at,
                    pinned_by_user_id=message.pinned_by_user_id,
                    user_name=user.email or user.phone_number if user else "System",
                    user_email=user.email if user else None,
                    reply_to=self._format_reply_message(reply_to_message) if reply_to_message else None
                )
                formatted_messages.append(formatted_message)
            
            # Reverse the list to show oldest first
            formatted_messages.reverse()
            
            # Update user's last read message
            if formatted_messages:
                membership.last_read_message_id = formatted_messages[-1].id
                membership.last_read_at = datetime.utcnow()
                membership.unread_count = 0
                self.db.commit()
            
            return MessageHistoryResponse(
                messages=formatted_messages,
                has_more=has_more,
                total_count=total_count,
                next_cursor=messages[-1].id if messages and has_more else None,
                prev_cursor=messages[0].id if messages else None
            )
            
        except Exception as e:
            logger.error(f"Error getting chat messages: {str(e)}")
            raise
    
    async def pin_message(self, chat_id: int, message_id: int, user_id: int, is_pinned: bool) -> ChatMessageResponse:
        """Pin or unpin a message (moderator only)"""
        try:
            # Check if user is a moderator
            membership = self.db.query(ChatMembership).filter(
                ChatMembership.chat_id == chat_id,
                ChatMembership.user_id == user_id,
                ChatMembership.is_active == True,
                ChatMembership.is_moderator == True
            ).first()
            
            if not membership:
                raise ValueError("User is not a moderator of this chat")
            
            # Get the message
            message = self.db.query(ChatMessage).filter(
                ChatMessage.id == message_id,
                ChatMessage.chat_id == chat_id,
                ChatMessage.is_deleted == False
            ).first()
            
            if not message:
                raise ValueError("Message not found")
            
            # Update pin status
            message.is_pinned = is_pinned
            message.pinned_by_user_id = user_id if is_pinned else None
            message.pinned_at = datetime.utcnow() if is_pinned else None
            
            # Set pin order for pinned messages
            if is_pinned:
                max_pin_order = self.db.query(func.max(ChatMessage.pin_order)).filter(
                    ChatMessage.chat_id == chat_id,
                    ChatMessage.is_pinned == True
                ).scalar() or 0
                message.pin_order = max_pin_order + 1
            else:
                message.pin_order = None
            
            self.db.commit()
            self.db.refresh(message)
            
            # Create response
            user = self.db.query(User).filter(User.id == message.user_id).first() if message.user_id else None
            response = ChatMessageResponse(
                id=message.id,
                chat_id=message.chat_id,
                user_id=message.user_id,
                message_content=message.message_content,
                message_type=message.message_type,
                is_pinned=message.is_pinned,
                is_deleted=message.is_deleted,
                is_edited=message.is_edited,
                pin_order=message.pin_order,
                thread_count=message.thread_count,
                created_at=message.created_at,
                edited_at=message.edited_at,
                pinned_at=message.pinned_at,
                pinned_by_user_id=message.pinned_by_user_id,
                user_name=user.email or user.phone_number if user else "System",
                user_email=user.email if user else None
            )
            
            # Broadcast pin/unpin event
            event_type = WebSocketMessageType.MESSAGE_PINNED if is_pinned else WebSocketMessageType.MESSAGE_UNPINNED
            await self.connection_manager.broadcast_to_chat(chat_id, {
                "type": event_type,
                "data": response.dict(),
                "user_id": user_id,
                "chat_id": chat_id
            })
            
            logger.info(f"Message {message_id} {'pinned' if is_pinned else 'unpinned'} by user {user_id}")
            return response
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error pinning/unpinning message: {str(e)}")
            raise
    
    async def close_chat(self, chat_id: int, reason: str = "Group completed") -> bool:
        """Close a chat and make it read-only"""
        try:
            chat = self.db.query(GroupChat).filter(GroupChat.id == chat_id).first()
            if not chat:
                raise ValueError("Chat not found")
            
            chat.is_read_only = True
            chat.closed_at = datetime.utcnow()
            
            # Send system message about closure
            await self.send_system_message(
                chat_id=chat_id,
                message=f"Chat has been closed. Reason: {reason}",
                message_type=MessageType.SYSTEM
            )
            
            self.db.commit()
            
            # Broadcast chat closure
            await self.connection_manager.broadcast_to_chat(chat_id, {
                "type": WebSocketMessageType.CHAT_CLOSED,
                "data": {
                    "reason": reason,
                    "closed_at": datetime.utcnow().isoformat()
                },
                "chat_id": chat_id
            })
            
            logger.info(f"Chat {chat_id} closed: {reason}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error closing chat: {str(e)}")
            raise
    
    def _format_reply_message(self, message: ChatMessage) -> Optional[dict]:
        """Format a reply-to message for response"""
        if not message:
            return None
        
        user = self.db.query(User).filter(User.id == message.user_id).first() if message.user_id else None
        
        return {
            "id": message.id,
            "user_name": user.email or user.phone_number if user else "System",
            "message_content": message.message_content[:100] + "..." if len(message.message_content) > 100 else message.message_content,
            "created_at": message.created_at.isoformat()
        }
    
    def _update_unread_counts(self, chat_id: int, latest_message_id: int, exclude_user_id: int):
        """Update unread counts for chat members"""
        try:
            # Update unread counts for all active members except the sender
            self.db.query(ChatMembership).filter(
                ChatMembership.chat_id == chat_id,
                ChatMembership.user_id != exclude_user_id,
                ChatMembership.is_active == True
            ).update({
                ChatMembership.unread_count: ChatMembership.unread_count + 1
            })
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating unread counts: {str(e)}")
    
    def get_chat_stats(self, chat_id: int) -> ChatStatsResponse:
        """Get statistics for a chat"""
        try:
            chat = self.db.query(GroupChat).filter(GroupChat.id == chat_id).first()
            if not chat:
                raise ValueError("Chat not found")
            
            # Count total messages
            total_messages = self.db.query(ChatMessage).filter(
                ChatMessage.chat_id == chat_id,
                ChatMessage.is_deleted == False
            ).count()
            
            # Count active members
            active_members = self.db.query(ChatMembership).filter(
                ChatMembership.chat_id == chat_id,
                ChatMembership.is_active == True
            ).count()
            
            # Count messages today
            today = datetime.utcnow().date()
            messages_today = self.db.query(ChatMessage).filter(
                ChatMessage.chat_id == chat_id,
                ChatMessage.is_deleted == False,
                func.date(ChatMessage.created_at) == today
            ).count()
            
            # Count pinned messages
            pinned_messages_count = self.db.query(ChatMessage).filter(
                ChatMessage.chat_id == chat_id,
                ChatMessage.is_pinned == True,
                ChatMessage.is_deleted == False
            ).count()
            
            return ChatStatsResponse(
                chat_id=chat_id,
                total_messages=total_messages,
                active_members=active_members,
                messages_today=messages_today,
                pinned_messages_count=pinned_messages_count
            )
            
        except Exception as e:
            logger.error(f"Error getting chat stats: {str(e)}")
            raise