"""
Test script to verify SQLAlchemy database connection with Supabase.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

def test_connection():
    """Test the database connection."""
    try:
        # Get database configuration from environment
        user = os.getenv("DB_USER", "postgres.xpypcbugicjtzjrtorse")
        password = os.getenv("DB_PASSWORD", "")
        host = os.getenv("DB_HOST", "aws-0-us-east-1.pooler.supabase.com")
        port = os.getenv("DB_PORT", "6543")
        dbname = os.getenv("DB_NAME", "postgres")
        
        # Construct the SQLAlchemy connection string
        database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}?sslmode=require"
        
        print(f"Testing connection to: {host}:{port}/{dbname}")
        print(f"User: {user}")
        
        
        # Create the SQLAlchemy engine with NullPool
        engine = create_engine(database_url, poolclass=NullPool)
        
        # Test the connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print("✅ Connection successful!")
            print(f"Test query result: {row[0]}")
            engine = create_engine(database_url)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            return True

            
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing SQLAlchemy database connection...")
    success = test_connection()
    
    if success:
        print("\n🎉 Database connection test passed!")
        print("The SQLAlchemy configuration is working correctly.")
    else:
        print("\n💥 Database connection test failed!")
        print("Please check your database configuration in the .env file.") 