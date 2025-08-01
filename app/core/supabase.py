from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.exceptions import DatabaseError, NotFoundError


class SupabaseManager:
    """Database connection manager using Supabase PostgreSQL with SQLAlchemy."""
    
    def __init__(self):
        # Construct the SQLAlchemy connection string
        self.database_url = f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?sslmode=require"
        
        # Create the SQLAlchemy engine with NullPool for transaction/session pooler
        self.engine = create_engine(self.database_url, poolclass=NullPool)
        
        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_session(self):
        """Get database session."""
        return self.SessionLocal()
    
    def test_connection(self):
        """Test database connection."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                return True
        except Exception as e:
            raise DatabaseError(f"Database connection failed: {str(e)}")
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        try:
            session = self.get_session()
            try:
                result = session.execute(
                    text("SELECT * FROM users WHERE id = :user_id"),
                    {"user_id": user_id}
                )
                row = result.fetchone()
                return dict(row._mapping) if row else None
            finally:
                session.close()
        except Exception as e:
            raise DatabaseError(f"Error fetching user: {str(e)}")
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        try:
            session = self.get_session()
            try:
                result = session.execute(
                    text("SELECT * FROM users WHERE email = :email"),
                    {"email": email}
                )
                row = result.fetchone()
                return dict(row._mapping) if row else None
            finally:
                session.close()
        except Exception as e:
            raise DatabaseError(f"Error fetching user: {str(e)}")
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user."""
        try:
            session = self.get_session()
            try:
                # Extract user data fields
                fields = list(user_data.keys())
                values = list(user_data.values())
                placeholders = [f":{field}" for field in fields]
                
                query = f"""
                    INSERT INTO users ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                    RETURNING *
                """
                
                result = session.execute(text(query), user_data)
                session.commit()
                row = result.fetchone()
                return dict(row._mapping) if row else None
            finally:
                session.close()
        except Exception as e:
            raise DatabaseError(f"Error creating user: {str(e)}")
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user data."""
        try:
            session = self.get_session()
            try:
                # Build dynamic update query
                set_clause = ", ".join([f"{field} = :{field}" for field in user_data.keys()])
                
                query = f"""
                    UPDATE users 
                    SET {set_clause}
                    WHERE id = :user_id
                    RETURNING *
                """
                
                # Add user_id to the parameters
                params = {**user_data, "user_id": user_id}
                
                result = session.execute(text(query), params)
                session.commit()
                row = result.fetchone()
                if row:
                    return dict(row._mapping)
                else:
                    raise NotFoundError("User not found")
            finally:
                session.close()
        except Exception as e:
            raise DatabaseError(f"Error updating user: {str(e)}")


# Create global instance
supabase = SupabaseManager() 