"""
Database initialization script for BigFarma.

This script automatically creates all database tables based on the current models.
No manual migration handling required.
"""

import logging
from sqlalchemy import create_engine
from app.database import Base
from .config.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get database URL from settings."""
    return f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?sslmode=require"


def init_database():
    """Initialize database with all tables from current models."""
    try:
        # Create engine
        engine = create_engine(get_database_url())
        
        # Create all tables based on current models
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Database tables created successfully!")
        logger.info("📋 Tables created:")
        
        # List created tables
        inspector = engine.dialect.inspector(engine)
        tables = inspector.get_table_names()
        for table in tables:
            logger.info(f"   - {table}")
            
        # Create upload directories
        create_upload_directories()
        
        logger.info("🎉 Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


def create_upload_directories():
    """Create upload directories for file storage."""
    import os
    
    directories = [
        "uploads",
        "uploads/avatars",
        "uploads/valid_ids",
        "uploads/farm_images"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Created directory: {directory}")


def drop_all_tables():
    """Drop all tables (use with caution!)."""
    try:
        engine = create_engine(get_database_url())
        Base.metadata.drop_all(bind=engine)
        logger.info("🗑️  All tables dropped successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error dropping tables: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        logger.warning("⚠️  Dropping all tables...")
        drop_all_tables()
    else:
        logger.info("🚀 Starting BigFarma database initialization...")
        init_database() 