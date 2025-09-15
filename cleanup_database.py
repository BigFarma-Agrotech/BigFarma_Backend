"""
Clean up existing orders and check enum state
"""
from sqlalchemy import text
from database import get_db, engine

def check_and_clean_orders():
    """Check current orders and clean if needed"""
    try:
        with engine.connect() as connection:
            print("🔍 Checking current database state...")
            
            # Check current enum values
            enum_result = connection.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'orderstatus'
                )
                ORDER BY enumlabel;
            """))
            
            enum_values = [row[0] for row in enum_result]
            print(f"📊 Current enum values: {enum_values}")
            
            # Check current orders and their statuses
            orders_result = connection.execute(text("""
                SELECT id, status, created_at 
                FROM orders 
                ORDER BY id;
            """))
            
            orders = list(orders_result)
            print(f"📋 Current orders ({len(orders)} total):")
            for order_id, status, created_at in orders:
                print(f"  Order {order_id}: {status} (created: {created_at})")
            
            if orders:
                print(f"\n🗑️  Would you like to delete existing orders to start fresh?")
                delete_choice = input("Delete all orders? (y/n): ").lower().strip()
                
                if delete_choice == 'y':
                    # Delete order issues first (foreign key constraint)
                    connection.execute(text("DELETE FROM order_issues;"))
                    # Delete order timeline entries
                    connection.execute(text("DELETE FROM order_timeline;"))
                    # Delete orders
                    connection.execute(text("DELETE FROM orders;"))
                    connection.commit()
                    print("✅ Deleted all existing orders and related data")
                else:
                    print("ℹ️  Keeping existing orders")
            
            print(f"\n🔧 Now let's fix the enum values...")
            
            # Add missing lowercase values
            needed_values = ['pending', 'confirmed', 'shipping', 'delivered', 'cancelled']
            
            for value in needed_values:
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
                    print(f"➕ Adding '{value}' to enum...")
                    connection.execute(text(f"ALTER TYPE orderstatus ADD VALUE '{value}';"))
                    connection.commit()  # Commit each enum addition
                else:
                    print(f"✅ '{value}' already exists")
            
            # Final check
            final_enum_result = connection.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'orderstatus'
                )
                ORDER BY enumlabel;
            """))
            
            final_enum_values = [row[0] for row in final_enum_result]
            print(f"✅ Final enum values: {final_enum_values}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🧹 Cleaning up database state...")
    success = check_and_clean_orders()
    
    if success:
        print("\n🎉 Database cleanup completed!")
        print("\n📋 Next steps:")
        print("1. Restart your FastAPI server: uvicorn main:app --reload")
        print("2. Create sample data: python create_sample_data.py")
        print("3. Test the API: python test_orders_api.py")
    else:
        print("\n💥 Cleanup failed.")
