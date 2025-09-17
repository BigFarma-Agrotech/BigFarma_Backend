"""
Script to fix missing order_numbers in existing orders
Using direct SQL queries to avoid ORM relationship issues
"""

from sqlalchemy import create_engine, text
from datetime import datetime
import random
import string
from config import settings

def generate_order_number(order_id: int, created_at: datetime) -> str:
    """Generate a unique order number for an order"""
    # Format: BF + YYYYMMDD + random 6 characters
    date_part = created_at.strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BF{date_part}{random_part}"

def fix_missing_order_numbers():
    """Update all orders that have missing order_numbers using direct SQL"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Find all orders without order_numbers
            result = conn.execute(text("""
                SELECT id, created_at 
                FROM orders 
                WHERE order_number IS NULL OR order_number = ''
            """))
            
            orders = result.fetchall()
            print(f"Found {len(orders)} orders without order numbers")
            
            if not orders:
                print("✅ All orders already have order numbers!")
                return
            
            # Update each order with a generated order number
            for order in orders:
                order_id = order[0]
                created_at = order[1]
                order_number = generate_order_number(order_id, created_at)
                
                conn.execute(
                    text("UPDATE orders SET order_number = :order_number WHERE id = :id"),
                    {"order_number": order_number, "id": order_id}
                )
                conn.commit()
                print(f"Updated Order ID {order_id} with order number: {order_number}")
            
            print(f"\nSuccessfully updated {len(orders)} orders")
            
            # Verify the update
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM orders 
                WHERE order_number IS NULL OR order_number = ''
            """))
            remaining = result.scalar()
            
            if remaining == 0:
                print("✅ All orders now have order numbers!")
            else:
                print(f"⚠️  Warning: {remaining} orders still missing order numbers")
                
    except Exception as e:
        print(f"❌ Error updating orders: {e}")

if __name__ == "__main__":
    print("Fixing missing order numbers...")
    print("Using direct SQL queries to avoid ORM issues")
    fix_missing_order_numbers()