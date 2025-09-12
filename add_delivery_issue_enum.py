"""
Add DELIVERY_ISSUE enum value to OrderStatus
"""
from sqlalchemy import text
from database import get_db, engine

def add_delivery_issue_enum():
    """Add DELIVERY_ISSUE value to the OrderStatus enum in PostgreSQL"""
    try:
        with engine.connect() as connection:
            # Check if the enum value already exists
            result = connection.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = 'delivery_issue' 
                    AND enumtypid = (
                        SELECT oid FROM pg_type WHERE typname = 'orderstatus'
                    )
                );
            """))
            
            exists = result.scalar()
            
            if not exists:
                print("Adding 'delivery_issue' to OrderStatus enum...")
                connection.execute(text("""
                    ALTER TYPE orderstatus ADD VALUE 'delivery_issue';
                """))
                connection.commit()
                print("✅ Successfully added 'delivery_issue' to OrderStatus enum")
            else:
                print("✅ 'delivery_issue' already exists in OrderStatus enum")
                
    except Exception as e:
        print(f"❌ Error adding enum value: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔧 Adding DELIVERY_ISSUE enum value to database...")
    success = add_delivery_issue_enum()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("You can now test the issue reporting functionality.")
    else:
        print("\n💥 Migration failed. Please check the error above.")
