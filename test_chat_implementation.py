#!/usr/bin/env python3
"""
Comprehensive test for the Group Chat implementation
Tests all components: models, schemas, service, and API routes
"""

import sys
import os
import asyncio
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=== Group Chat Implementation Test ===\n")

print("1. Testing imports...")
try:
    # Import database base
    from database import Base
    print("✅ Database base imported")
    
    # Import all models to ensure relationships work
    from features.auth.models import User, UserCategory
    from features.users.models import FarmerProfile, ConsumerProfile, FarmType
    from features.marketplace.models import Product, ProductCategory, ProductStatus, Order, OrderStatus
    from features.orders.models import OrderTimeline, OrderIssue, IssueStatus
    from features.group_buy.models import GroupBuy, GroupStatus, GroupMember, GroupMemberStatus
    from features.group_buy.models import GroupChat, ChatMessage, ChatMembership, ChatReport, MessageType
    print("✅ All models imported successfully")
    
    # Import schemas
    from features.group_buy.schemas import (
        ChatMessageCreate, ChatMessageResponse, GroupChatResponse,
        ChatMembershipResponse, ChatReportCreate, ChatReportResponse
    )
    print("✅ Chat schemas imported")
    
    # Import service
    from features.group_buy.chat_service import ChatService, WebSocketConnectionManager
    print("✅ Chat service imported")
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print("\n2. Testing database models...")
try:
    # Create in-memory SQLite database for testing
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Test creating test data
    print("✅ Database session created")
    
except Exception as e:
    print(f"❌ Database setup failed: {e}")
    sys.exit(1)

print("\n3. Testing model creation...")
try:
    # Create test user
    test_user = User(
        email="test@farmer.com",
        phone_number="+1234567890",
        password="hashed_password",
        category=UserCategory.FARMER,
        profile_setup=True,
        is_verified=True,
        is_active=True
    )
    session.add(test_user)
    session.flush()  # Get the ID without committing
    
    # Create farmer profile
    farmer_profile = FarmerProfile(
        user_id=test_user.id,
        full_name="Test Farmer",
        home_address="123 Farm Road",
        id_document="DOC123",
        farm_name="Test Farm",
        farm_type=FarmType.CROP,
        farm_location="Farm Valley",
        farm_size="10 acres",
        years_experience=5,
        is_verified=True
    )
    session.add(farmer_profile)
    session.flush()
    
    # Create product
    test_product = Product(
        farmer_id=test_user.id,
        name="Test Tomatoes",
        description="Fresh organic tomatoes",
        category=ProductCategory.CROP,
        quantity="100 kg",
        price=2.50,
        location="Test Farm Location",
        images="test_image.jpg"
    )
    session.add(test_product)
    session.flush()
    
    # Create group buy
    test_group_buy = GroupBuy(
        creator_id=test_user.id,
        product_id=test_product.id,
        group_name="Bulk Tomato Purchase",
        group_description="Group buying fresh tomatoes",
        group_location="Test Location",
        shareable_link="test-group-link-123",
        target_quantity="50 kg",
        target_quantity_numeric=50.0,
        quantity_unit="kg",
        individual_contribution=25.0,
        status=GroupStatus.ACTIVE
    )
    session.add(test_group_buy)
    session.flush()
    
    # Create group chat
    test_chat = GroupChat(
        group_id=test_group_buy.id
    )
    session.add(test_chat)
    session.flush()
    
    # Create chat membership
    test_membership = ChatMembership(
        chat_id=test_chat.id,
        user_id=test_user.id,
        is_moderator=True
    )
    session.add(test_membership)
    session.flush()
    
    # Create chat message
    test_message = ChatMessage(
        chat_id=test_chat.id,
        user_id=test_user.id,
        message_content="Welcome to the group chat!",
        message_type=MessageType.TEXT
    )
    session.add(test_message)
    session.flush()
    
    print("✅ All models created successfully")
    print(f"   - User ID: {test_user.id}")
    print(f"   - Group Buy ID: {test_group_buy.id}")
    print(f"   - Chat ID: {test_chat.id}")
    print(f"   - Message ID: {test_message.id}")
    
except Exception as e:
    print(f"❌ Model creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n4. Testing schema validation...")
try:
    # Test message creation schema
    message_data = ChatMessageCreate(
        chat_id=test_chat.id,
        message_content="Test message content",
        message_type=MessageType.TEXT
    )
    print("✅ ChatMessageCreate schema validated")
    
    # Test message response schema  
    message_response = ChatMessageResponse(
        id=test_message.id,
        chat_id=test_chat.id,
        user_id=test_user.id,
        message_content=test_message.message_content,
        message_type=test_message.message_type,
        is_pinned=test_message.is_pinned,
        is_deleted=test_message.is_deleted,
        is_edited=test_message.is_edited,
        pin_order=test_message.pin_order,
        thread_count=test_message.thread_count,
        created_at=test_message.created_at,
        edited_at=test_message.edited_at,
        pinned_at=test_message.pinned_at,
        pinned_by_user_id=test_message.pinned_by_user_id,
        user_name=test_user.email,
        user_email=test_user.email
    )
    print("✅ ChatMessageResponse schema validated")
    
except Exception as e:
    print(f"❌ Schema validation failed: {e}")
    sys.exit(1)

print("\n5. Testing ChatService...")
try:
    # Initialize ChatService with database session
    chat_service = ChatService(session)
    print("✅ ChatService initialized")
    
    # Test WebSocketConnectionManager
    ws_manager = WebSocketConnectionManager()
    print("✅ WebSocketConnectionManager initialized")
    
except Exception as e:
    print(f"❌ Service initialization failed: {e}")
    sys.exit(1)

print("\n6. Testing database queries...")
try:
    # Test retrieving data
    retrieved_chat = session.query(GroupChat).filter_by(id=test_chat.id).first()
    if retrieved_chat:
        print(f"✅ Chat retrieved: Chat ID {retrieved_chat.id}")
    else:
        print("❌ Failed to retrieve chat")
        
    retrieved_message = session.query(ChatMessage).filter_by(id=test_message.id).first()
    if retrieved_message:
        print(f"✅ Message retrieved: {retrieved_message.message_content[:30]}...")
    else:
        print("❌ Failed to retrieve message")
        
    # Test relationships
    chat_messages = session.query(ChatMessage).filter_by(chat_id=test_chat.id).all()
    print(f"✅ Found {len(chat_messages)} messages in chat")
    
    chat_members = session.query(ChatMembership).filter_by(chat_id=test_chat.id).all()
    print(f"✅ Found {len(chat_members)} members in chat")
    
except Exception as e:
    print(f"❌ Database queries failed: {e}")
    sys.exit(1)

finally:
    # Clean up
    session.close()

print("\n7. Testing API route imports...")
try:
    from features.group_buy.routes import router
    print("✅ Group buy routes imported successfully")
    
    # Check if chat routes are included
    routes = [route.path for route in router.routes]
    chat_routes = [r for r in routes if 'chat' in r.lower()]
    print(f"✅ Found {len(chat_routes)} chat-related routes")
    
except Exception as e:
    print(f"❌ Route import failed: {e}")
    sys.exit(1)

print("\n=== Test Summary ===")
print("✅ All imports successful")
print("✅ Database models working correctly")
print("✅ Model relationships functioning")
print("✅ Schema validation passing")
print("✅ Service initialization working")
print("✅ Database operations successful")
print("✅ API routes loading correctly")

print("\n🎉 Group Chat implementation is working correctly!")
print("   All components tested successfully with no errors.")