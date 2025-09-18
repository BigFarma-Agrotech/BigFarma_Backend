"""
Database migration script to sync SQLAlchemy models with database
Automatically adds missing columns to all tables
"""
import os
import sys
from sqlalchemy import inspect, text, Column, Table
from sqlalchemy.schema import CreateTable, AddConstraint
from sqlalchemy.dialects.postgresql import ENUM

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, SessionLocal, Base
from config import settings

def get_all_models():
    """Get all SQLAlchemy models from Base metadata"""
    return Base.metadata.tables

def get_existing_columns(table_name):
    """Get existing columns in a table"""
    inspector = inspect(engine)
    return [col['name'] for col in inspector.get_columns(table_name)]

def get_model_columns(table_name):
    """Get columns defined in SQLAlchemy model"""
    table = Base.metadata.tables[table_name]
    return [column.name for column in table.columns]

def migrate_database():
    """Automatically add missing columns to all database tables"""
    
    print(f"🔄 Running database migrations...")
    print(f"Database: {settings.DATABASE_URL}")
    
    db = SessionLocal()
    
    try:
        # Get all tables from models
        all_tables = get_all_models()
        print(f"Found {len(all_tables)} tables in models")
        
        # Check each table
        for table_name in all_tables:
            print(f"\n📊 Checking table: {table_name}")
            
            try:
                # Get existing columns in database
                existing_columns = get_existing_columns(table_name)
                print(f"   Existing columns: {len(existing_columns)}")
                
                # Get columns defined in model
                model_columns = get_model_columns(table_name)
                print(f"   Model columns: {len(model_columns)}")
                
                # Find missing columns
                missing_columns = set(model_columns) - set(existing_columns)
                
                if missing_columns:
                    print(f"   ➕ Missing columns: {list(missing_columns)}")
                    
                    # Add each missing column
                    table = Base.metadata.tables[table_name]
                    for column_name in missing_columns:
                        column = table.columns[column_name]
                        
                        # Generate SQL for adding column
                        column_type = column.type.compile(engine.dialect)
                        
                        # Handle default values
                        default_clause = ""
                        if column.default is not None:
                            if hasattr(column.default, 'arg'):
                                default_value = column.default.arg
                                if default_value is not None:
                                    if isinstance(default_value, bool):
                                        default_value = str(default_value).lower()
                                    default_clause = f"DEFAULT {default_value}"
                            elif callable(column.default):
                                # For functions like func.now()
                                default_clause = f"DEFAULT CURRENT_TIMESTAMP"
                        
                        # Handle nullable
                        nullable_clause = "NULL" if column.nullable else "NOT NULL"
                        
                        # Build SQL statement
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable_clause}"
                        if default_clause:
                            sql += f" {default_clause}"
                        
                        try:
                            print(f"      Adding: {column_name} ({column_type})")
                            db.execute(text(sql))
                            db.commit()
                            print(f"      ✅ Added: {column_name}")
                            
                        except Exception as e:
                            print(f"      ⚠️ Failed to add {column_name}: {str(e)}")
                            db.rollback()
                            # Try without default if it failed
                            try:
                                sql_simple = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable_clause}"
                                db.execute(text(sql_simple))
                                db.commit()
                                print(f"      ✅ Added {column_name} (without default)")
                            except Exception as e2:
                                print(f"      ❌ Could not add {column_name}: {str(e2)}")
                                db.rollback()
                
                else:
                    print(f"   ✅ Table {table_name} is up to date")
                    
            except Exception as e:
                print(f"   ⚠️ Error checking table {table_name}: {str(e)}")
                continue
        
        # Additional specific migrations (for enums, constraints, etc.)
        additional_migrations = [
            {
                "description": "Add profile_setup to users table if missing",
                "sql": "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_setup BOOLEAN DEFAULT FALSE;"
            },
            {
                "description": "Add full_name to farmer_profiles table if missing",
                "sql": "ALTER TABLE farmer_profiles ADD COLUMN IF NOT EXISTS full_name VARCHAR;"
            },
            {
                "description": "Update order status enum values",
                "sql": """
                DO $$ 
                BEGIN
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
                END $$;
                """
            }
        ]
        
        print(f"\n🔧 Running additional migrations...")
        for migration in additional_migrations:
            try:
                print(f"   Running: {migration['description']}")
                db.execute(text(migration['sql']))
                db.commit()
                print(f"   ✅ Success: {migration['description']}")
            except Exception as e:
                print(f"   ⚠️ Warning: {migration['description']} - {str(e)}")
                db.rollback()
        
        print("\n" + "="*50)
        print("✅ Database migration completed!")
        print("💡 Some warnings are normal if columns/tables already exist")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def check_database_status():
    """Check the current status of database vs models"""
    print(f"🔍 Checking database status...")
    
    db = SessionLocal()
    
    try:
        inspector = inspect(engine)
        db_tables = inspector.get_table_names()
        
        print(f"Database tables: {len(db_tables)}")
        print(f"Model tables: {len(Base.metadata.tables)}")
        
        for table_name in Base.metadata.tables:
            if table_name not in db_tables:
                print(f"❌ Missing table: {table_name}")
            else:
                # Check columns
                db_columns = [col['name'] for col in inspector.get_columns(table_name)]
                model_columns = [col.name for col in Base.metadata.tables[table_name].columns]
                
                missing_columns = set(model_columns) - set(db_columns)
                if missing_columns:
                    print(f"⚠️  Table '{table_name}' missing columns: {list(missing_columns)}")
                else:
                    print(f"✅ Table '{table_name}' is complete")
    
    finally:
        db.close()

if __name__ == "__main__":
    # Check status first
    check_database_status()
    
    # Ask for confirmation
    response = input("\nDo you want to run migrations? (y/N): ")
    if response.lower() in ['y', 'yes']:
        migrate_database()
    else:
        print("Migration cancelled.")