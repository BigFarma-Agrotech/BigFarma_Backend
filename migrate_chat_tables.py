"""
Database Migration Script for Group Chat Feature

This script adds the necessary tables and relationships for the group chat functionality.
Run this script after the existing group_buy tables are in place.

Migration: Add chat tables
Date: October 2025
Tables: group_chats, chat_messages, chat_memberships, chat_reports
"""

from sqlalchemy import text
from database import engine, get_db
import logging

logger = logging.getLogger(__name__)

# SQL statements for creating chat tables
CREATE_CHAT_TABLES = [
    """
    -- Create MessageType enum
    CREATE TYPE messagetype AS ENUM (
        'text', 'system', 'announcement', 'join_notification', 
        'leave_notification', 'progress_update', 'completion_notice'
    );
    """,
    
    """
    -- Create group_chats table
    CREATE TABLE group_chats (
        id SERIAL PRIMARY KEY,
        group_id INTEGER UNIQUE NOT NULL REFERENCES group_buys(id) ON DELETE CASCADE,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        is_read_only BOOLEAN DEFAULT FALSE NOT NULL,
        allow_member_invite BOOLEAN DEFAULT TRUE NOT NULL,
        auto_close_on_completion BOOLEAN DEFAULT TRUE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
        closed_at TIMESTAMP WITH TIME ZONE,
        last_message_at TIMESTAMP WITH TIME ZONE
    );
    """,
    
    """
    -- Create chat_messages table
    CREATE TABLE chat_messages (
        id SERIAL PRIMARY KEY,
        chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        message_content TEXT NOT NULL,
        message_type messagetype DEFAULT 'text' NOT NULL,
        is_pinned BOOLEAN DEFAULT FALSE NOT NULL,
        is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
        is_edited BOOLEAN DEFAULT FALSE NOT NULL,
        pin_order INTEGER,
        reply_to_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
        thread_count INTEGER DEFAULT 0 NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
        edited_at TIMESTAMP WITH TIME ZONE,
        pinned_at TIMESTAMP WITH TIME ZONE,
        pinned_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
    );
    """,
    
    """
    -- Create chat_memberships table
    CREATE TABLE chat_memberships (
        id SERIAL PRIMARY KEY,
        chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        is_muted BOOLEAN DEFAULT FALSE NOT NULL,
        is_moderator BOOLEAN DEFAULT FALSE NOT NULL,
        last_read_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
        last_read_at TIMESTAMP WITH TIME ZONE,
        unread_count INTEGER DEFAULT 0 NOT NULL,
        joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
        left_at TIMESTAMP WITH TIME ZONE,
        notify_on_mention BOOLEAN DEFAULT TRUE NOT NULL,
        notify_on_all_messages BOOLEAN DEFAULT TRUE NOT NULL,
        UNIQUE(chat_id, user_id)
    );
    """,
    
    """
    -- Create chat_reports table
    CREATE TABLE chat_reports (
        id SERIAL PRIMARY KEY,
        chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
        message_id INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
        reported_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        reported_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        report_reason VARCHAR NOT NULL,
        report_description TEXT,
        status VARCHAR DEFAULT 'pending' NOT NULL,
        reviewed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        resolution_notes TEXT,
        reported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
        reviewed_at TIMESTAMP WITH TIME ZONE
    );
    """
]

# Create indexes for better performance
CREATE_INDEXES = [
    """
    -- Indexes for chat_messages table
    CREATE INDEX idx_chat_messages_chat_id_created_at ON chat_messages(chat_id, created_at DESC);
    CREATE INDEX idx_chat_messages_user_id ON chat_messages(user_id);
    CREATE INDEX idx_chat_messages_pinned ON chat_messages(chat_id, is_pinned) WHERE is_pinned = TRUE;
    CREATE INDEX idx_chat_messages_reply_to ON chat_messages(reply_to_message_id) WHERE reply_to_message_id IS NOT NULL;
    CREATE INDEX idx_chat_messages_content_search ON chat_messages USING gin(to_tsvector('english', message_content));
    """,
    
    """
    -- Indexes for chat_memberships table
    CREATE INDEX idx_chat_memberships_chat_id ON chat_memberships(chat_id);
    CREATE INDEX idx_chat_memberships_user_id ON chat_memberships(user_id);
    CREATE INDEX idx_chat_memberships_active ON chat_memberships(chat_id, is_active) WHERE is_active = TRUE;
    CREATE INDEX idx_chat_memberships_unread ON chat_memberships(user_id, unread_count) WHERE unread_count > 0;
    """,
    
    """
    -- Indexes for group_chats table
    CREATE INDEX idx_group_chats_group_id ON group_chats(group_id);
    CREATE INDEX idx_group_chats_active ON group_chats(is_active) WHERE is_active = TRUE;
    CREATE INDEX idx_group_chats_last_message ON group_chats(last_message_at DESC) WHERE last_message_at IS NOT NULL;
    """,
    
    """
    -- Indexes for chat_reports table
    CREATE INDEX idx_chat_reports_chat_id ON chat_reports(chat_id);
    CREATE INDEX idx_chat_reports_status ON chat_reports(status);
    CREATE INDEX idx_chat_reports_reported_by ON chat_reports(reported_by_user_id);
    """
]

# Add chat relationship to group_buys table (if not exists)
ADD_CHAT_RELATIONSHIP = [
    """
    -- This relationship is handled in the SQLAlchemy models
    -- No additional SQL needed for the relationship
    """
]

def run_migration():
    """Run the chat tables migration"""
    try:
        logger.info("Starting chat tables migration...")
        
        with engine.connect() as connection:
            # Start transaction
            trans = connection.begin()
            
            try:
                # Create tables
                logger.info("Creating chat tables...")
                for sql in CREATE_CHAT_TABLES:
                    logger.info(f"Executing: {sql[:100]}...")
                    connection.execute(text(sql))
                
                # Create indexes
                logger.info("Creating indexes...")
                for sql in CREATE_INDEXES:
                    logger.info(f"Executing: {sql[:100]}...")
                    connection.execute(text(sql))
                
                # Commit transaction
                trans.commit()
                logger.info("Chat tables migration completed successfully!")
                
                return True
                
            except Exception as e:
                trans.rollback()
                logger.error(f"Error during migration: {e}")
                raise
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

def rollback_migration():
    """Rollback the chat tables migration"""
    try:
        logger.info("Rolling back chat tables migration...")
        
        rollback_sql = [
            "DROP TABLE IF EXISTS chat_reports CASCADE;",
            "DROP TABLE IF EXISTS chat_memberships CASCADE;", 
            "DROP TABLE IF EXISTS chat_messages CASCADE;",
            "DROP TABLE IF EXISTS group_chats CASCADE;",
            "DROP TYPE IF EXISTS messagetype CASCADE;"
        ]
        
        with engine.connect() as connection:
            trans = connection.begin()
            
            try:
                for sql in rollback_sql:
                    logger.info(f"Executing: {sql}")
                    connection.execute(text(sql))
                
                trans.commit()
                logger.info("Chat tables rollback completed successfully!")
                return True
                
            except Exception as e:
                trans.rollback()
                logger.error(f"Error during rollback: {e}")
                raise
                
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False

def check_tables_exist():
    """Check if chat tables already exist"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('group_chats', 'chat_messages', 'chat_memberships', 'chat_reports')
                ORDER BY table_name;
            """))
            
            existing_tables = [row[0] for row in result]
            
            if existing_tables:
                logger.info(f"Found existing chat tables: {existing_tables}")
                return existing_tables
            else:
                logger.info("No chat tables found")
                return []
                
    except Exception as e:
        logger.error(f"Error checking tables: {e}")
        return None

if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        print("Rolling back chat tables migration...")
        success = rollback_migration()
    elif len(sys.argv) > 1 and sys.argv[1] == "--check":
        print("Checking for existing chat tables...")
        tables = check_tables_exist()
        if tables:
            print(f"Existing tables: {', '.join(tables)}")
        else:
            print("No chat tables found")
        sys.exit(0)
    else:
        # Check if tables already exist
        existing_tables = check_tables_exist()
        if existing_tables:
            print(f"Warning: Some chat tables already exist: {existing_tables}")
            print("Use --rollback to remove them first, or proceed with caution")
            
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("Migration cancelled")
                sys.exit(0)
        
        print("Running chat tables migration...")
        success = run_migration()
    
    if success:
        print("Migration completed successfully!")
        sys.exit(0)
    else:
        print("Migration failed!")
        sys.exit(1)