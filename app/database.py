import logging
from typing import Optional
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

from .config.config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy setup
Base = declarative_base()

# Database connection
def get_database_url() -> str:
    """Get database URL from settings."""
    return f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?sslmode=require"

# Create engine
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Database models
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OTP(Base):
    __tablename__ = "otps"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    otp_code = Column(String, nullable=False)
    otp_type = Column(String, nullable=False)  # email, phone
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, unique=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    avatar_url = Column(String)
    bio = Column(Text)
    date_of_birth = Column(DateTime)
    gender = Column(String)
    address = Column(Text)
    city = Column(String)
    state = Column(String)
    country = Column(String)
    postal_code = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def create_tables() -> None:
    """Create database tables if they don't exist."""
    try:
        logger.info("Database tables creation initiated")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables creation completed")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise


def get_db_session() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize database connection
def init_database() -> None:
    """Initialize database connection."""
    try:
        # Test the connection
        with engine.connect() as connection:
            logger.info("Database connection initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise 