"""
Database migration script to add missing columns to orders table
Run this before creating sample data
"""
import os
import sys
from sqlalchemy import text

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, SessionLocal
from config import settings

def migrate_database():
    """Add missing columns to existing database tables"""
    
    print(f"🔄 Running database migrations...")
    print(f"Database: {settings.DATABASE_URL}")
    
    db = SessionLocal()
    
    try:
        # List of migrations to run
        migrations = [
            {
                "description": "Add contact_phone to orders table",
                "sql": "ALTER TABLE orders ADD COLUMN IF NOT EXISTS contact_phone VARCHAR;"
            },
            {
                "description": "Add delivery_notes to orders table", 
                "sql": "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_notes TEXT;"
            },
            {
                "description": "Add order_number to orders table",
                "sql": "ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_number VARCHAR UNIQUE;"
            },
            {
                "description": "Add estimated_delivery_date to orders table",
                "sql": "ALTER TABLE orders ADD COLUMN IF NOT EXISTS estimated_delivery_date TIMESTAMP WITH TIME ZONE;"
            },
            {
                "description": "Create order_timeline table",
                "sql": """
                CREATE TABLE IF NOT EXISTS order_timeline (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(id),
                    status VARCHAR NOT NULL,
                    title VARCHAR NOT NULL,
                    description TEXT,
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            },
            {
                "description": "Create order_issues table",
                "sql": """
                CREATE TABLE IF NOT EXISTS order_issues (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(id),
                    consumer_id INTEGER REFERENCES users(id),
                    issue_description TEXT NOT NULL,
                    status VARCHAR DEFAULT 'reported',
                    admin_response TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE
                );
                """
            },
            {
                "description": "Add new order status enum values",
                "sql": """
                DO $$ 
                BEGIN
                    -- Add new enum values if they don't exist
                    BEGIN
                        ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'awaiting_confirmation';
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END;
                    
                    BEGIN
                        ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'delivery_issue';
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END;
                EXCEPTION
                    -- If the enum type doesn't exist, it will be created by SQLAlchemy
                    WHEN undefined_object THEN null;
                END $$;
                """
            }
        ]
        
        # Run each migration
        for migration in migrations:
            try:
                print(f"   Running: {migration['description']}")
                db.execute(text(migration['sql']))
                db.commit()
                print(f"   ✅ Success: {migration['description']}")
            except Exception as e:
                print(f"   ⚠️ Warning: {migration['description']} - {str(e)}")
                db.rollback()
                # Continue with other migrations
                continue
        
        print("\n✅ Database migration completed!")
        print("\n💡 Note: Some warnings are normal if columns/tables already exist")
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_database()
