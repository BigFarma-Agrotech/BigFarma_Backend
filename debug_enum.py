"""
Debug and fix OrderStatus enum values
"""
from sqlalchemy import text
from database import get_db, engine
from features.marketplace.models import OrderStatus

def check_enum_values():
    """Check what enum values exist in the database"""
    try:
        with engine.connect() as connection:
            # Get all enum values from the database
            result = connection.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'orderstatus'
                )
                ORDER BY enumlabel;
            """))
            
            db_values = [row[0] for row in result]
            print("📊 Database enum values:", db_values)
            
            # Get Python enum values
            python_values = [status.value for status in OrderStatus]
            print("🐍 Python enum values:", python_values)
            
            # Check for mismatches
            missing_in_db = set(python_values) - set(db_values)
            extra_in_db = set(db_values) - set(python_values)
            
            if missing_in_db:
                print(f"❌ Missing in database: {missing_in_db}")
            if extra_in_db:
                print(f"⚠️ Extra in database: {extra_in_db}")
            
            if not missing_in_db and not extra_in_db:
                print("✅ All enum values match!")
                
    except Exception as e:
        print(f"❌ Error checking enum values: {e}")

def fix_enum_case():
    """Add the uppercase version or fix the case issue"""
    try:
        with engine.connect() as connection:
            # Check if DELIVERY_ISSUE (uppercase) exists
            result = connection.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = 'DELIVERY_ISSUE' 
                    AND enumtypid = (
                        SELECT oid FROM pg_type WHERE typname = 'orderstatus'
                    )
                );
            """))
            
            exists_upper = result.scalar()
            
            if not exists_upper:
                print("Adding 'DELIVERY_ISSUE' (uppercase) to OrderStatus enum...")
                connection.execute(text("""
                    ALTER TYPE orderstatus ADD VALUE 'DELIVERY_ISSUE';
                """))
                connection.commit()
                print("✅ Added 'DELIVERY_ISSUE' (uppercase)")
            else:
                print("✅ 'DELIVERY_ISSUE' (uppercase) already exists")
                
    except Exception as e:
        print(f"❌ Error fixing enum case: {e}")

def test_enum_assignment():
    """Test setting OrderStatus values"""
    print("\n🧪 Testing enum assignments...")
    for status in OrderStatus:
        print(f"  {status.name} = '{status.value}'")

if __name__ == "__main__":
    print("🔍 Debugging OrderStatus enum...")
    check_enum_values()
    print("\n🔧 Fixing enum case...")
    fix_enum_case()
    print("\n🔍 Checking again after fix...")
    check_enum_values()
    test_enum_assignment()
