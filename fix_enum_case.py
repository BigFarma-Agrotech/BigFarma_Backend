"""
Fix OrderStatus enum case consistency
Convert all database enum values to lowercase to match Python enum
"""
from sqlalchemy import text
from database import get_db, engine

def fix_enum_case_consistency():
    """Fix the case consistency for OrderStatus enum values"""
    try:
        with engine.connect() as connection:
            print("🔧 Starting enum case consistency fix...")
            
            # First, let's see what we're working with
            result = connection.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'orderstatus'
                )
                ORDER BY enumlabel;
            """))
            
            current_values = [row[0] for row in result]
            print(f"Current database enum values: {current_values}")
            
            # Check if we have any orders using ANY values
            all_status_check = connection.execute(text("""
                SELECT DISTINCT status, COUNT(*) 
                FROM orders 
                GROUP BY status;
            """))
            
            status_usage = list(all_status_check)
            print(f"📊 Current order statuses in use: {status_usage}")
            
            # Step 1: Add missing lowercase enum values if they don't exist
            print("➕ Adding missing lowercase enum values...")
            needed_values = ['pending', 'confirmed', 'shipping', 'delivered', 'cancelled']
            added_any = False
            
            for value in needed_values:
                # Check if it already exists
                check_result = connection.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_enum 
                        WHERE enumlabel = :value
                        AND enumtypid = (
                            SELECT oid FROM pg_type WHERE typname = 'orderstatus'
                        )
                    );
                """), {"value": value})
                
                if not check_result.scalar():
                    print(f"  Adding '{value}'...")
                    connection.execute(text(f"ALTER TYPE orderstatus ADD VALUE '{value}';"))
                    added_any = True
                else:
                    print(f"  '{value}' already exists")
            
            # IMPORTANT: Commit the new enum values before using them
            if added_any:
                print("💾 Committing new enum values...")
                connection.commit()
            
            # Step 2: Update existing order records to use lowercase
            print("🔄 Updating existing order records to lowercase...")
            
            updates = [
                ("PENDING", "pending"),
                ("CONFIRMED", "confirmed"), 
                ("SHIPPING", "shipping"),
                ("DELIVERED", "delivered"),
                ("CANCELLED", "cancelled"),
                ("DELIVERY_ISSUE", "delivery_issue")
            ]
            
            for old_val, new_val in updates:
                result = connection.execute(text(f"""
                    UPDATE orders SET status = '{new_val}' WHERE status = '{old_val}';
                """))
                if result.rowcount > 0:
                    print(f"  Updated {result.rowcount} records: {old_val} → {new_val}")
            
            # Commit the updates
            connection.commit()
            print("✅ Successfully updated order records!")
            
            # Verify the current state
            updated_status_check = connection.execute(text("""
                SELECT DISTINCT status, COUNT(*) 
                FROM orders 
                GROUP BY status;
            """))
            
            updated_usage = list(updated_status_check)
            print(f"📊 Updated order statuses: {updated_usage}")
            
            # Verify enum values
            result = connection.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'orderstatus'
                )
                ORDER BY enumlabel;
            """))
            
            final_values = [row[0] for row in result]
            print(f"✅ Final database enum values: {final_values}")
            
    except Exception as e:
        print(f"❌ Error fixing enum case: {e}")
        try:
            connection.rollback()
        except:
            pass
        return False
    
    return True

if __name__ == "__main__":
    print("🔧 Fixing OrderStatus enum case consistency...")
    success = fix_enum_case_consistency()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("✅ All enum values are now lowercase and consistent")
        print("🔄 Please restart your FastAPI server: uvicorn main:app --reload")
        print("🧪 Then test again: python test_orders_api.py")
    else:
        print("\n💥 Migration failed. Please check the error above.")