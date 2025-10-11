import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc

from features.group_buy.models import GroupBuy, GroupMember, GroupTransaction, GroupNotification, GroupJoinRequest, GroupStatus, GroupMemberStatus, MessageType
from features.group_buy.schemas import (
    GroupBuyCreate, GroupBuyUpdate, GroupMemberCreate, GroupMemberJoin,
    GroupTransactionCreate, GroupNotificationCreate, GroupProgressResponse,
    GroupDiscoveryRequest, GroupPublicResponse,
    GroupJoinRequest as GroupJoinRequestSchema, GroupJoinResponse,
    GroupPricingRequest, GroupPricingResponse, GroupJoinValidationResponse
)
from features.marketplace.models import Product, AvailabilityStatus
from features.auth.models import User

logger = logging.getLogger(__name__)

class GroupBuyService:
    def __init__(self, db: Session):
        self.db = db

    async def create_group(self, creator_id: int, group_data: GroupBuyCreate) -> GroupBuy:
        """Create a new group buy"""
        try:
            # Resolve product ID if product_name was provided instead
            product_id = group_data.product_id
            if not product_id and group_data.product_name:
                product = self.db.query(Product).filter(
                    Product.name.ilike(f"%{group_data.product_name}%"),
                    Product.availability == AvailabilityStatus.IN_STOCK,
                    Product.is_listed == True
                ).first()
                if product:
                    product_id = product.id
                else:
                    raise ValueError(f"Product '{group_data.product_name}' not found or not available")
            
            # Validate product exists and is available
            product = self.db.query(Product).filter(
                Product.id == product_id,
                Product.availability == AvailabilityStatus.IN_STOCK,
                Product.is_listed == True
            ).first()
            
            if not product:
                raise ValueError("Product not found or not available")
            
            # Auto-calculate individual_contribution if not provided
            individual_contribution = group_data.individual_contribution
            if not individual_contribution:
                # Calculate as product price divided by estimated 10 members
                estimated_members = 10
                total_cost = product.price * group_data.target_quantity_numeric
                individual_contribution = total_cost / estimated_members
            
            # Validate quantity unit (already validated in schema)
            quantity_unit = group_data.quantity_unit
            
            # Generate unique shareable link
            shareable_link = self._generate_shareable_link()
            
            # Create group
            group = GroupBuy(
                group_name=group_data.group_name,
                group_description=group_data.group_description,
                group_location=group_data.group_location,
                product_id=product_id,
                target_quantity=group_data.target_quantity,
                target_quantity_numeric=group_data.target_quantity_numeric,
                quantity_unit=quantity_unit,
                creator_id=creator_id,
                individual_contribution=individual_contribution,
                shareable_link=shareable_link,
                status=GroupStatus.ACTIVE,
                is_public=group_data.is_public,
                max_members=group_data.max_members,
                deadline=group_data.deadline
            )
            
            self.db.add(group)
            self.db.flush()  # Get the ID
            
            # Add creator as first member
            creator_member = GroupMember(
                group_id=group.id,
                user_id=creator_id,
                status=GroupMemberStatus.ACTIVE,
                joined_at=datetime.utcnow(),
                contribution_amount=individual_contribution,
                quantity_committed=group_data.target_quantity_numeric / 10  # Creator commits to 10% initially
            )
            
            self.db.add(creator_member)
            self.db.commit()
            self.db.refresh(group)
            
            # Create group chat
            try:
                from features.group_buy.chat_service import ChatService
                chat_service = ChatService(self.db)
                await chat_service.create_group_chat(group.id)
                logger.info(f"Chat created for group {group.id}")
            except Exception as chat_error:
                logger.warning(f"Failed to create chat for group {group.id}: {chat_error}")
                # Don't fail the entire group creation if chat creation fails
            
            # Send notification to creator
            self._send_notification(
                group_id=group.id,
                user_id=creator_id,
                notification_type="group_created",
                title="Group Created Successfully",
                message=f"Your group '{group.group_name}' has been created. Share the link to invite others!"
            )
            
            logger.info(f"Group {group.id} created by user {creator_id}")
            return group
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating group: {str(e)}")
            raise

    async def join_group(self, user_id: int, join_data: GroupMemberJoin) -> GroupMember:
        """Join an existing group"""
        try:
            # Check if group exists and is active
            group = self.db.query(GroupBuy).filter(
                GroupBuy.id == join_data.group_id,
                GroupBuy.status == GroupStatus.ACTIVE
            ).first()
            
            if not group:
                raise ValueError("Group not found or not active")
            
            # Check if user is already a member
            existing_member = self.db.query(GroupMember).filter(
                GroupMember.group_id == join_data.group_id,
                GroupMember.user_id == user_id,
                GroupMember.status.in_([GroupMemberStatus.ACTIVE, GroupMemberStatus.PENDING])
            ).first()
            
            if existing_member:
                raise ValueError("User is already a member of this group")
            
            # Check if group has space (optional limit)
            current_members = self.db.query(GroupMember).filter(
                GroupMember.group_id == join_data.group_id,
                GroupMember.status == GroupMemberStatus.ACTIVE
            ).count()
            
            # Create member record
            member = GroupMember(
                group_id=join_data.group_id,
                user_id=user_id,
                status=GroupMemberStatus.ACTIVE,
                joined_at=datetime.utcnow(),
                contribution_amount=join_data.contribution_amount,
                quantity_committed=join_data.quantity_committed
            )
            
            self.db.add(member)
            self.db.commit()
            self.db.refresh(member)
            
            # Update group progress
            self._update_group_progress(join_data.group_id)
            
            # Add user to group chat
            try:
                from features.group_buy.chat_service import ChatService
                chat_service = ChatService(self.db)
                
                # Get or create chat for the group
                chat = group.chat
                if not chat:
                    chat = await chat_service.create_group_chat(join_data.group_id)
                
                # Add member to chat
                await chat_service.add_member_to_chat(chat.id, user_id)
                logger.info(f"User {user_id} added to chat for group {join_data.group_id}")
            except Exception as chat_error:
                logger.warning(f"Failed to add user {user_id} to chat for group {join_data.group_id}: {chat_error}")
            
            # Send notifications
            self._send_notification(
                group_id=join_data.group_id,
                user_id=user_id,
                notification_type="member_joined",
                title="Welcome to the Group!",
                message=f"You've successfully joined the group '{group.group_name}'"
            )
            
            # Notify other members
            self._notify_group_members(
                group_id=join_data.group_id,
                exclude_user_id=user_id,
                notification_type="new_member",
                title="New Member Joined",
                message="A new member has joined your group!"
            )
            
            logger.info(f"User {user_id} joined group {join_data.group_id}")
            return member
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error joining group: {str(e)}")
            raise

    def get_group_details(self, group_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get detailed group information"""
        group = self.db.query(GroupBuy).options(
            joinedload(GroupBuy.product),
            joinedload(GroupBuy.creator),
            joinedload(GroupBuy.members).joinedload(GroupMember.user),
            joinedload(GroupBuy.transactions)
        ).filter(GroupBuy.id == group_id).first()
        
        if not group:
            raise ValueError("Group not found")
        
        # Get members with their details
        members = []
        for member in group.members:
            member_data = {
                "id": member.id,
                "user_id": member.user_id,
                "user_name": member.user.email or member.user.phone_number,
                "status": member.status,
                "contribution_amount": member.contribution_amount,
                "quantity_committed": member.quantity_committed,
                "joined_at": member.joined_at,
                "left_at": member.left_at
            }
            members.append(member_data)
        
        # Get transactions
        transactions = []
        for transaction in group.transactions:
            transaction_data = {
                "id": transaction.id,
                "amount": transaction.amount,
                "transaction_type": transaction.transaction_type,
                "payment_method": transaction.payment_method,
                "status": transaction.status,
                "created_at": transaction.created_at,
                "completed_at": transaction.completed_at
            }
            transactions.append(transaction_data)
        
        return {
            "group": {
                "id": group.id,
                "group_name": group.group_name,
                "group_description": group.group_description,
                "group_location": group.group_location,
                "shareable_link": group.shareable_link,
                "status": group.status,
                "current_quantity": group.current_quantity,
                "target_quantity": group.target_quantity,
                "target_quantity_numeric": group.target_quantity_numeric,
                "quantity_unit": group.quantity_unit,
                "progress_percentage": group.progress_percentage,
                "group_wallet_balance": group.group_wallet_balance,
                "individual_contribution": group.individual_contribution,
                "created_at": group.created_at,
                "updated_at": group.updated_at,
                "completed_at": group.completed_at,
                "locked_at": group.locked_at
            },
            "product": {
                "id": group.product.id,
                "name": group.product.name,
                "category": group.product.category,
                "price": group.product.price,
                "location": group.product.location,
                "images": group.product.images,
                "availability": group.product.availability
            },
            "creator": {
                "id": group.creator.id,
                "email": group.creator.email,
                "phone_number": group.creator.phone_number
            },
            "members": members,
            "transactions": transactions,
            "is_member": user_id in [m.user_id for m in group.members if m.status == GroupMemberStatus.ACTIVE] if user_id else False,
            "is_creator": group.creator_id == user_id if user_id else False
        }

    def get_group_progress(self, group_id: int) -> GroupProgressResponse:
        """Get group progress information"""
        group = self.db.query(GroupBuy).filter(GroupBuy.id == group_id).first()
        if not group:
            raise ValueError("Group not found")
        
        # Calculate days remaining (if group has a deadline)
        days_remaining = None
        estimated_completion_date = None
        
        # Get active members count
        members_count = self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.status == GroupMemberStatus.ACTIVE
        ).count()
        
        return GroupProgressResponse(
            group_id=group_id,
            current_quantity=group.current_quantity,
            target_quantity=group.target_quantity_numeric,
            progress_percentage=group.progress_percentage,
            members_count=members_count,
            total_contributions=group.group_wallet_balance,
            days_remaining=days_remaining,
            estimated_completion_date=estimated_completion_date
        )

    async def add_contribution(self, group_id: int, user_id: int, amount: float, payment_method: str = "wallet") -> GroupTransaction:
        """Add a contribution to the group wallet"""
        try:
            # Check if user is an active member
            member = self.db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status == GroupMemberStatus.ACTIVE
            ).first()
            
            if not member:
                raise ValueError("User is not an active member of this group")
            
            # Create transaction
            transaction = GroupTransaction(
                group_id=group_id,
                member_id=member.id,
                amount=amount,
                transaction_type="contribution",
                payment_method=payment_method,
                status="completed"
            )
            
            self.db.add(transaction)
            
            # Update member contribution
            member.contribution_amount += amount
            
            # Update group wallet
            group = self.db.query(GroupBuy).filter(GroupBuy.id == group_id).first()
            group.group_wallet_balance += amount
            
            self.db.commit()
            self.db.refresh(transaction)
            
            # Update progress
            self._update_group_progress(group_id)
            
            # Check if group should be locked for purchase
            await self._check_and_trigger_purchase(group_id)
            
            logger.info(f"Contribution of {amount} added to group {group_id} by user {user_id}")
            return transaction
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding contribution: {str(e)}")
            raise

    def _update_group_progress(self, group_id: int):
        """Update group progress and check for completion"""
        group = self.db.query(GroupBuy).filter(GroupBuy.id == group_id).first()
        if not group:
            return
        
        # Calculate current quantity from active members
        active_members = self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.status == GroupMemberStatus.ACTIVE
        ).all()
        
        current_quantity = sum(member.quantity_committed for member in active_members)
        progress_percentage = (current_quantity / group.target_quantity_numeric) * 100
        
        # Update group
        group.current_quantity = current_quantity
        group.progress_percentage = min(progress_percentage, 100.0)
        
        self.db.commit()
        
        # Send progress notification if significant change
        if progress_percentage >= 25 and progress_percentage < 50:
            self._notify_group_members(
                group_id=group_id,
                notification_type="progress_update",
                title="25% Progress Reached!",
                message=f"Your group has reached {progress_percentage:.1f}% of the target quantity!"
            )
        elif progress_percentage >= 50 and progress_percentage < 75:
            self._notify_group_members(
                group_id=group_id,
                notification_type="progress_update",
                title="50% Progress Reached!",
                message=f"Your group has reached {progress_percentage:.1f}% of the target quantity!"
            )
        elif progress_percentage >= 75 and progress_percentage < 100:
            self._notify_group_members(
                group_id=group_id,
                notification_type="progress_update",
                title="75% Progress Reached!",
                message=f"Your group has reached {progress_percentage:.1f}% of the target quantity!"
            )

    async def _check_and_trigger_purchase(self, group_id: int):
        """Check if group has reached target and trigger auto-purchase"""
        group = self.db.query(GroupBuy).filter(GroupBuy.id == group_id).first()
        if not group:
            return
        
        # Check if target is reached
        if group.progress_percentage >= 100.0 and group.status == GroupStatus.ACTIVE:
            # Lock the group
            group.status = GroupStatus.LOCKED
            group.locked_at = datetime.utcnow()
            
            self.db.commit()
            
            # Close group chat and send completion message
            try:
                from features.group_buy.chat_service import ChatService
                chat_service = ChatService(self.db)
                if group.chat:
                    # Send completion message to chat
                    await chat_service.send_system_message(
                        chat_id=group.chat.id,
                        message="🎉 Congratulations! The group has reached its target quantity and the purchase has been automatically triggered! The chat will now be closed.",
                        message_type=MessageType.COMPLETION_NOTICE
                    )
                    
                    # Close the chat
                    await chat_service.close_chat(group.chat.id, "Group purchase completed")
                    logger.info(f"Chat closed for completed group {group_id}")
            except Exception as chat_error:
                logger.warning(f"Failed to close chat for group {group_id}: {chat_error}")
            
            # Notify all members
            self._notify_group_members(
                group_id=group_id,
                notification_type="purchase_triggered",
                title="Purchase Triggered!",
                message="Your group has reached the target quantity and the purchase has been automatically triggered!"
            )
            
            # TODO: Implement actual purchase logic here
            # This would involve:
            # 1. Creating a bulk order
            # 2. Processing payments
            # 3. Coordinating delivery
            # 4. Updating group status to COMPLETED
            
            logger.info(f"Group {group_id} purchase triggered - target quantity reached")

    def _generate_shareable_link(self) -> str:
        """Generate a unique shareable link for the group"""
        unique_id = str(uuid.uuid4())[:8]
        return f"https://bigfarma.com/group/{unique_id}"

    def _send_notification(self, group_id: int, user_id: int, notification_type: str, title: str, message: str):
        """Send a notification to a specific user"""
        notification = GroupNotification(
            group_id=group_id,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message
        )
        
        self.db.add(notification)
        self.db.commit()

    def _notify_group_members(self, group_id: int, exclude_user_id: Optional[int] = None, 
                            notification_type: str = "group_update", title: str = "Group Update", 
                            message: str = "There's an update to your group"):
        """Send notification to all active group members"""
        members = self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.status == GroupMemberStatus.ACTIVE
        )
        
        if exclude_user_id:
            members = members.filter(GroupMember.user_id != exclude_user_id)
        
        for member in members:
            self._send_notification(
                group_id=group_id,
                user_id=member.user_id,
                notification_type=notification_type,
                title=title,
                message=message
            )

    def get_user_groups(self, user_id: int, status: Optional[GroupStatus] = None) -> List[Dict[str, Any]]:
        """Get all groups for a user"""
        query = self.db.query(GroupBuy).join(GroupMember).filter(
            GroupMember.user_id == user_id,
            GroupMember.status == GroupMemberStatus.ACTIVE
        )
        
        if status:
            query = query.filter(GroupBuy.status == status)
        
        groups = query.all()
        
        result = []
        for group in groups:
            group_data = {
                "id": group.id,
                "group_name": group.group_name,
                "group_description": group.group_description,
                "group_location": group.group_location,
                "status": group.status,
                "progress_percentage": group.progress_percentage,
                "current_quantity": group.current_quantity,
                "target_quantity": group.target_quantity,
                "quantity_unit": group.quantity_unit,
                "created_at": group.created_at,
                "is_creator": group.creator_id == user_id
            }
            result.append(group_data)
        
        return result

    def leave_group(self, group_id: int, user_id: int) -> bool:
        """Leave a group"""
        try:
            member = self.db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status == GroupMemberStatus.ACTIVE
            ).first()
            
            if not member:
                raise ValueError("User is not a member of this group")
            
            # Check if user is the creator
            group = self.db.query(GroupBuy).filter(GroupBuy.id == group_id).first()
            if group.creator_id == user_id:
                raise ValueError("Group creator cannot leave the group")
            
            # Update member status
            member.status = GroupMemberStatus.LEFT
            member.left_at = datetime.utcnow()
            
            # Update group progress
            self._update_group_progress(group_id)
            
            # Notify other members
            self._notify_group_members(
                group_id=group_id,
                exclude_user_id=user_id,
                notification_type="member_left",
                title="Member Left Group",
                message="A member has left your group"
            )
            
            self.db.commit()
            logger.info(f"User {user_id} left group {group_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error leaving group: {str(e)}")
            raise

    def cancel_group(self, group_id: int, user_id: int) -> bool:
        """Cancel a group (only creator can cancel)"""
        try:
            group = self.db.query(GroupBuy).filter(
                GroupBuy.id == group_id,
                GroupBuy.creator_id == user_id,
                GroupBuy.status == GroupStatus.ACTIVE
            ).first()
            
            if not group:
                raise ValueError("Group not found or user is not the creator")
            
            # Update group status
            group.status = GroupStatus.CANCELLED
            
            # Update all members status
            self.db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.status == GroupMemberStatus.ACTIVE
            ).update({"status": GroupMemberStatus.LEFT})
            
            # Notify all members
            self._notify_group_members(
                group_id=group_id,
                notification_type="group_cancelled",
                title="Group Cancelled",
                message="The group has been cancelled by the creator"
            )
            
            self.db.commit()
            logger.info(f"Group {group_id} cancelled by user {user_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cancelling group: {str(e)}")
            raise

    def update_group(self, group_id: int, user_id: int, update_data: GroupBuyUpdate) -> GroupBuy:
        """Update a group (only creator can update)"""
        try:
            group = self.db.query(GroupBuy).filter(
                GroupBuy.id == group_id,
                GroupBuy.creator_id == user_id,
                GroupBuy.status == GroupStatus.ACTIVE
            ).first()
            
            if not group:
                raise ValueError("Group not found or user is not the creator")
            
            # Check if group has members (restrict certain updates)
            current_members = self.db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.status == GroupMemberStatus.ACTIVE
            ).count()
            
            # Update allowed fields
            if update_data.group_name is not None:
                group.group_name = update_data.group_name
            
            if update_data.group_description is not None:
                group.group_description = update_data.group_description
            
            if update_data.group_location is not None:
                group.group_location = update_data.group_location
            
            # Only allow quantity updates if no members have joined
            if current_members == 0:
                if update_data.target_quantity is not None:
                    group.target_quantity = update_data.target_quantity
                
                if update_data.target_quantity_numeric is not None:
                    group.target_quantity_numeric = update_data.target_quantity_numeric
                
                if update_data.quantity_unit is not None:
                    group.quantity_unit = update_data.quantity_unit
                
                if update_data.individual_contribution is not None:
                    group.individual_contribution = update_data.individual_contribution
            else:
                # If members exist, only allow minor updates
                if update_data.target_quantity is not None or update_data.target_quantity_numeric is not None:
                    raise ValueError("Cannot change target quantity when group has members")
                
                if update_data.individual_contribution is not None:
                    raise ValueError("Cannot change individual contribution when group has members")
            
            self.db.commit()
            self.db.refresh(group)
            
            # Send notification to members about group update
            self._notify_group_members(
                group_id=group_id,
                notification_type="group_updated",
                title="Group Updated",
                message="The group details have been updated by the creator"
            )
            
            logger.info(f"Group {group_id} updated by user {user_id}")
            return group
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating group: {str(e)}")
            raise

        def delete_group(self, group_id: int, user_id: int) -> bool:
            """Delete a group (only creator can delete, only empty or cancelled groups)"""
            try:
            # Check if group exists and user is the creator
                group = self.db.query(GroupBuy).filter(
                GroupBuy.id == group_id,
                GroupBuy.creator_id == user_id
                ).first()
            
                if not group:
                    raise ValueError("Group not found or user is not the creator")
            
            # Only allow deletion of empty groups or cancelled groups
                if group.status == GroupStatus.ACTIVE:
                # Check if group has any active members
                    active_members = self.db.query(GroupMember).filter(
                    GroupMember.group_id == group_id,
                    GroupMember.status == GroupMemberStatus.ACTIVE
                    ).count()
                
                    if active_members > 1:  # Allow if only creator is member
                        raise ValueError("Cannot delete group with active members. Cancel the group first.")
            
            # Check for pending join requests
                pending_requests = self.db.query(GroupJoinRequest).filter(
                GroupJoinRequest.group_id == group_id,
                GroupJoinRequest.status == "pending"
                ).count()
            
                if pending_requests > 0:
                    raise ValueError("Cannot delete group with pending join requests. Cancel the group first.")
            
                # Notify all members about group deletion
                if group.status == GroupStatus.ACTIVE:
                    self._notify_group_members(
                        group_id=group_id,
                        notification_type="group_deleted",
                        title="Group Deleted",
                    message="The group has been permanently deleted by the creator"
                    )
            
                # Delete the group (cascade will handle related entities)
                self.db.delete(group)
                self.db.commit()
            
                logger.info(f"Group {group_id} deleted by user {user_id}")
                return True
            
            except Exception as e:
                self.db.rollback()
                logger.error(f"Error deleting group: {str(e)}")
                raise

    # Group Discovery and Public Access Methods
    def get_public_groups(self, discovery_request: GroupDiscoveryRequest, skip: int = 0, limit: int = 20) -> List[GroupPublicResponse]:
        """Get public groups for discovery and browsing"""
        try:
            query = self.db.query(GroupBuy).options(
                joinedload(GroupBuy.product),
                joinedload(GroupBuy.creator)
            ).filter(
                GroupBuy.is_public == True,
                GroupBuy.status == GroupStatus.ACTIVE
            )
            
            # Apply filters
            if discovery_request.location:
                query = query.filter(GroupBuy.group_location.ilike(f"%{discovery_request.location}%"))
            
            if discovery_request.product_name:
                query = query.join(Product).filter(Product.name.ilike(f"%{discovery_request.product_name}%"))
            
            if discovery_request.category:
                query = query.join(Product).filter(Product.category == discovery_request.category)
            
            if discovery_request.min_price:
                query = query.filter(GroupBuy.individual_contribution >= discovery_request.min_price)
            
            if discovery_request.max_price:
                query = query.filter(GroupBuy.individual_contribution <= discovery_request.max_price)
            
            # Apply sorting
            if discovery_request.sort_by == "newest":
                query = query.order_by(desc(GroupBuy.created_at))
            elif discovery_request.sort_by == "oldest":
                query = query.order_by(GroupBuy.created_at)
            elif discovery_request.sort_by == "price_asc":
                query = query.order_by(GroupBuy.individual_contribution)
            elif discovery_request.sort_by == "price_desc":
                query = query.order_by(desc(GroupBuy.individual_contribution))
            elif discovery_request.sort_by == "progress":
                query = query.order_by(desc(GroupBuy.progress_percentage))
            
            groups = query.offset(skip).limit(limit).all()
            
            result = []
            for group in groups:
                # Calculate slots remaining
                current_members = self.db.query(GroupMember).filter(
                    GroupMember.group_id == group.id,
                    GroupMember.status == GroupMemberStatus.ACTIVE
                ).count()
                
                slots_remaining = (group.max_members - current_members) if group.max_members else None
                
                group_data = GroupPublicResponse(
                    id=group.id,
                    group_name=group.group_name,
                    group_description=group.group_description,
                    group_location=group.group_location,
                    product_name=group.product.name,
                    product_category=group.product.category,
                    product_price=group.product.price,
                    target_quantity=group.target_quantity,
                    quantity_unit=group.quantity_unit,
                    progress_percentage=group.progress_percentage,
                    current_quantity=group.current_quantity,
                    target_quantity_numeric=group.target_quantity_numeric,
                    slots_remaining=slots_remaining or 999,  # No limit if max_members is None
                    max_members=group.max_members,
                    members_count=current_members,
                    individual_contribution=group.individual_contribution,
                    deadline=group.deadline,
                    created_at=group.created_at,
                    is_public=group.is_public
                )
                result.append(group_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching public groups: {str(e)}")
            raise

    def get_public_group_details(self, group_id: int) -> Dict[str, Any]:
        """Get public group details for non-members"""
        try:
            group = self.db.query(GroupBuy).options(
                joinedload(GroupBuy.product),
                joinedload(GroupBuy.creator),
                joinedload(GroupBuy.members).joinedload(GroupMember.user)
            ).filter(
                GroupBuy.id == group_id,
                GroupBuy.is_public == True,
                GroupBuy.status == GroupStatus.ACTIVE
            ).first()
            
            if not group:
                raise ValueError("Group not found or not public")
            
            # Calculate slots remaining
            current_members = self.db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.status == GroupMemberStatus.ACTIVE
            ).count()
            
            slots_remaining = (group.max_members - current_members) if group.max_members else None
            
            return {
                "group": {
                    "id": group.id,
                    "group_name": group.group_name,
                    "group_description": group.group_description,
                    "group_location": group.group_location,
                    "status": group.status,
                    "progress_percentage": group.progress_percentage,
                    "current_quantity": group.current_quantity,
                    "target_quantity": group.target_quantity,
                    "target_quantity_numeric": group.target_quantity_numeric,
                    "quantity_unit": group.quantity_unit,
                    "individual_contribution": group.individual_contribution,
                    "slots_remaining": slots_remaining,
                    "max_members": group.max_members,
                    "deadline": group.deadline,
                    "created_at": group.created_at
                },
                "product": {
                    "id": group.product.id,
                    "name": group.product.name,
                    "category": group.product.category,
                    "price": group.product.price,
                    "location": group.product.location,
                    "images": group.product.images,
                    "availability": group.product.availability
                },
                "creator": {
                    "id": group.creator.id,
                    "name": group.creator.email or group.creator.phone_number
                },
                "members_count": current_members,
                "is_public": group.is_public
            }
            
        except Exception as e:
            logger.error(f"Error fetching public group details: {str(e)}")
            raise

    def validate_group_join(self, group_id: int, user_id: int) -> GroupJoinValidationResponse:
        """Validate if a user can join a group"""
        try:
            group = self.db.query(GroupBuy).filter(
                GroupBuy.id == group_id,
                GroupBuy.is_public == True,
                GroupBuy.status == GroupStatus.ACTIVE
            ).first()
            
            if not group:
                return GroupJoinValidationResponse(
                    can_join=False,
                    reason="Group not found or not public",
                    slots_available=0,
                    max_members=None,
                    deadline=None,
                    conflicts=[]
                )
            
            # Check if user is already a member
            existing_member = self.db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status.in_([GroupMemberStatus.ACTIVE, GroupMemberStatus.PENDING])
            ).first()
            
            if existing_member:
                return GroupJoinValidationResponse(
                    can_join=False,
                    reason="User is already a member of this group",
                    slots_available=0,
                    max_members=group.max_members,
                    deadline=group.deadline,
                    conflicts=["already_member"]
                )
            
            # Check member limit
            current_members = self.db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.status == GroupMemberStatus.ACTIVE
            ).count()
            
            if group.max_members and current_members >= group.max_members:
                return GroupJoinValidationResponse(
                    can_join=False,
                    reason="Group is full",
                    slots_available=0,
                    max_members=group.max_members,
                    deadline=group.deadline,
                    conflicts=["group_full"]
                )
            
            # Check deadline
            if group.deadline and group.deadline < datetime.utcnow():
                return GroupJoinValidationResponse(
                    can_join=False,
                    reason="Group deadline has passed",
                    slots_available=group.max_members - current_members if group.max_members else 999,
                    max_members=group.max_members,
                    deadline=group.deadline,
                    conflicts=["deadline_passed"]
                )
            
            slots_available = (group.max_members - current_members) if group.max_members else 999
            
            return GroupJoinValidationResponse(
                can_join=True,
                reason=None,
                slots_available=slots_available,
                max_members=group.max_members,
                deadline=group.deadline,
                conflicts=[]
            )
            
        except Exception as e:
            logger.error(f"Error validating group join: {str(e)}")
            raise

    def calculate_group_pricing(self, group_id: int, quantity: float) -> GroupPricingResponse:
        """Calculate pricing for a specific quantity in a group"""
        try:
            group = self.db.query(GroupBuy).filter(GroupBuy.id == group_id).first()
            if not group:
                raise ValueError("Group not found")
            
            # Get product price
            product = self.db.query(Product).filter(Product.id == group.product_id).first()
            if not product:
                raise ValueError("Product not found")
            
            unit_price = product.price
            total_price = unit_price * quantity
            
            # Calculate discount (placeholder - could be based on quantity or group size)
            discount_percentage = 0.0  # TODO: Implement actual discount logic
            savings_amount = total_price * (discount_percentage / 100)
            final_price = total_price - savings_amount
            
            return GroupPricingResponse(
                group_id=group_id,
                quantity=quantity,
                unit_price=unit_price,
                total_price=final_price,
                discount_percentage=discount_percentage,
                savings_amount=savings_amount
            )
            
        except Exception as e:
            logger.error(f"Error calculating group pricing: {str(e)}")
            raise

    def request_group_join(self, user_id: int, join_request: GroupJoinRequestSchema) -> GroupJoinResponse:
        """Request to join a group (with payment placeholder)"""
        try:
            # Validate group exists and is public
            group = self.db.query(GroupBuy).filter(
                GroupBuy.id == join_request.group_id,
                GroupBuy.is_public == True,
                GroupBuy.status == GroupStatus.ACTIVE
            ).first()
            
            if not group:
                raise ValueError("Group not found or not public")
            
            # Validate user can join
            validation = self.validate_group_join(join_request.group_id, user_id)
            if not validation.can_join:
                raise ValueError(validation.reason)
            
            # Create join request
            join_request_db = GroupJoinRequest(
                group_id=join_request.group_id,
                user_id=user_id,
                quantity_requested=join_request.quantity_requested,
                contribution_amount=join_request.contribution_amount,
                payment_method=join_request.payment_method,
                payment_status="pending",  # Placeholder
                status="pending"
            )
            
            self.db.add(join_request_db)
            self.db.commit()
            self.db.refresh(join_request_db)
            
            # TODO: Implement actual payment processing
            # For now, we'll simulate successful payment
            join_request_db.payment_status = "completed"
            join_request_db.status = "approved"
            join_request_db.approved_at = datetime.utcnow()
            
            # Add user as group member
            member = GroupMember(
                group_id=join_request.group_id,
                user_id=user_id,
                status=GroupMemberStatus.ACTIVE,
                joined_at=datetime.utcnow(),
                contribution_amount=join_request.contribution_amount,
                quantity_committed=join_request.quantity_requested
            )
            
            self.db.add(member)
            self.db.commit()
            
            # Update group progress
            self._update_group_progress(join_request.group_id)
            
            # Send notifications
            self._send_notification(
                group_id=join_request.group_id,
                user_id=user_id,
                notification_type="member_joined",
                title="Successfully Joined Group!",
                message=f"You've successfully joined the group '{group.group_name}'"
            )
            
            # Notify other members
            self._notify_group_members(
                group_id=join_request.group_id,
                exclude_user_id=user_id,
                notification_type="new_member",
                title="New Member Joined",
                message="A new member has joined your group!"
            )
            
            logger.info(f"User {user_id} joined group {join_request.group_id}")
            
            return GroupJoinResponse(
                id=join_request_db.id,
                group_id=join_request_db.group_id,
                user_id=join_request_db.user_id,
                quantity_requested=join_request_db.quantity_requested,
                contribution_amount=join_request_db.contribution_amount,
                payment_status=join_request_db.payment_status,
                payment_method=join_request_db.payment_method,
                status=join_request_db.status,
                created_at=join_request_db.created_at
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error requesting group join: {str(e)}")
            raise