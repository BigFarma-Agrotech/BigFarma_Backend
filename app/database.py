import logging
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Boolean, DateTime, Text, Enum
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import enum

from .config.config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy setup
Base = declarative_base()

# User categories enum
class UserCategory(str, enum.Enum):
    """User categories for the platform."""
    FARMER = "farmer"
    CONSUMER = "consumer"

# Database connection
def get_database_url() -> str:
    """Get database URL from settings."""
    return f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?sslmode=require"

# Create engine
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=False)
    user_category = Column(Enum(UserCategory), nullable=True)
    is_active = Column(Boolean, default=False)
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
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    avatar_url = Column(String)
    address = Column(Text, nullable=False)
    phone = Column(String)
    email = Column(String)
    user_category = Column(Enum(UserCategory), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, unique=True, nullable=False)
    valid_id_url = Column(String, nullable=False)
    farm_type = Column(String, nullable=False)
    farm_image_url = Column(String)
    farm_location = Column(Text, nullable=False)
    farm_size = Column(String)
    years_experience = Column(Integer)
    is_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConsumerProfile(Base):
    __tablename__ = "consumer_profiles"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, unique=True, nullable=False)
    product_preferences = Column(Text, default='[]')
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