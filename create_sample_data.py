"""
Sample data generator for BigFarma Backend - Uses only existing enum values
Run this script to populate the database with test data
"""
import os
import sys
from datetime import datetime, timedelta
import uuid

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine
from database import Base
from config import settings
from features.auth.models import User, UserCategory
from features.users.models import FarmerProfile, ConsumerProfile, FarmType
from features.marketplace.models import Product, Order, Review, ProductCategory, AvailabilityStatus, OrderStatus
from features.orders.models import OrderTimeline, OrderIssue, OrderTimelineStatus, IssueStatus
from features.auth.service import AuthService
from core.security import get_password_hash

def create_sample_data():
    """Create comprehensive sample data for testing"""
    
    print(f"Using database: {settings.DATABASE_URL}")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"Database already has {existing_users} users. Continue? (y/n)")
            response = input().lower().strip()
            if response != 'y':
                print("Cancelled")
                return
            
        print("Creating sample users...")
        
        # Sample Farmers - using correct field names and enum values
        farmers_data = [
            {
                "email": "john.farmer@bigfarma.com",
                "phone": "+234-800-555-0001", 
                "password": "farmer123",
                "profile": {
                    "full_name": "John Doe",
                    "home_address": "15 Farm Road, Ikeja, Lagos State",
                    "id_document": "https://example.com/id_john.jpg",
                    "farm_name": "GreenRoots Farm",
                    "farm_location": "Ikeja, Lagos",
                    "farm_type": FarmType.CROP,
                    "farm_size": "5 acres",
                    "years_experience": 10
                }
            },
            {
                "email": "mary.adaku@bigfarma.com",
                "phone": "+234-800-555-0002",
                "password": "farmer123", 
                "profile": {
                    "full_name": "Mary Adaku",
                    "home_address": "23 Adaku Street, Garki, Abuja FCT",
                    "id_document": "https://example.com/id_mary.jpg", 
                    "farm_name": "Adaku Farm",
                    "farm_location": "Abuja, FCT",
                    "farm_type": FarmType.MIXED,
                    "farm_size": "12 acres",
                    "years_experience": 15
                }
            }
        ]
        
        farmers = []
        for farmer_data in farmers_data:
            existing_user = db.query(User).filter(User.email == farmer_data["email"]).first()
            if existing_user:
                print(f"   Farmer {farmer_data['email']} already exists")
                farmers.append(existing_user)
                continue
                
            user = User(
                email=farmer_data["email"],
                phone_number=farmer_data["phone"],
                password=get_password_hash(farmer_data["password"]),
                category=UserCategory.FARMER,
                is_verified=True
            )
            db.add(user)
            db.flush()
            
            profile = FarmerProfile(
                user_id=user.id,
                full_name=farmer_data["profile"]["full_name"],
                home_address=farmer_data["profile"]["home_address"], 
                id_document=farmer_data["profile"]["id_document"],
                farm_name=farmer_data["profile"]["farm_name"],
                farm_location=farmer_data["profile"]["farm_location"],
                farm_type=farmer_data["profile"]["farm_type"],
                farm_size=farmer_data["profile"]["farm_size"],
                years_experience=farmer_data["profile"]["years_experience"],
                is_verified=True
            )
            db.add(profile)
            farmers.append(user)
        
        # Sample Consumers - using correct field names
        consumers_data = [
            {
                "email": "jane.consumer@bigfarma.com",
                "phone": "+234-800-555-1001",
                "password": "consumer123",
                "profile": {
                    "first_name": "Jane",
                    "last_name": "Smith", 
                    "address": "Victoria Island, Lagos"
                }
            },
            {
                "email": "ahmed.buyer@bigfarma.com",
                "phone": "+234-800-555-1002",
                "password": "consumer123",
                "profile": {
                    "first_name": "Ahmed",
                    "last_name": "Musa",
                    "address": "Garki, Abuja"
                }
            }
        ]
        
        consumers = []
        for consumer_data in consumers_data:
            existing_user = db.query(User).filter(User.email == consumer_data["email"]).first()
            if existing_user:
                print(f"   Consumer {consumer_data['email']} already exists")
                consumers.append(existing_user)
                continue
                
            user = User(
                email=consumer_data["email"],
                phone_number=consumer_data["phone"],
                password=get_password_hash(consumer_data["password"]),
                category=UserCategory.CONSUMER,
                is_verified=True
            )
            db.add(user)
            db.flush()
            
            profile = ConsumerProfile(
                user_id=user.id,
                first_name=consumer_data["profile"]["first_name"],
                last_name=consumer_data["profile"]["last_name"],
                address=consumer_data["profile"]["address"]
            )
            db.add(profile)
            consumers.append(user)
        
        db.commit()
        print(f"Created {len(farmers)} farmers and {len(consumers)} consumers")
        
        # Create sample products
        print("Creating sample products...")
        products_data = [
            {
                "farmer_id": farmers[0].id,
                "name": "Fresh Tomatoes (Basket)",
                "category": ProductCategory.CROP,
                "description": "Fresh, red tomatoes harvested this morning",
                "quantity": "1 basket (25kg)",
                "price": 5000.0,
                "discount_percentage": 0.0,
                "location": "Ikeja, Lagos",
                "images": "tomato1.jpg,tomato2.jpg"
            },
            {
                "farmer_id": farmers[1].id,
                "name": "Fresh Peppers (Basket)",
                "category": ProductCategory.CROP,
                "description": "Spicy red peppers, perfect for cooking",
                "quantity": "1 basket (15kg)",
                "price": 8000.0,
                "discount_percentage": 15.0,
                "location": "Abuja, FCT",
                "images": "pepper1.jpg"
            }
        ]
        
        products = []
        for product_data in products_data:
            existing_product = db.query(Product).filter(
                Product.farmer_id == product_data["farmer_id"],
                Product.name == product_data["name"]
            ).first()
            if existing_product:
                print(f"   Product '{product_data['name']}' already exists")
                products.append(existing_product)
                continue
                
            product = Product(
                farmer_id=product_data["farmer_id"],
                name=product_data["name"],
                category=product_data["category"],
                description=product_data["description"],
                quantity=product_data["quantity"],
                price=product_data["price"],
                discount_percentage=product_data["discount_percentage"],
                location=product_data["location"],
                images=product_data["images"],
                is_approved=True,
                is_listed=True,
                availability=AvailabilityStatus.IN_STOCK
            )
            db.add(product)
            products.append(product)
        
        db.commit()
        print(f"Created {len(products)} products")
        
        # Create sample orders using ONLY existing enum values
        print("Creating sample orders...")
        orders_data = [
            {
                "product": products[0],
                "consumer": consumers[0],
                "status": OrderStatus.DELIVERED,  # Existing enum
                "days_ago": 5
            },
            {
                "product": products[1],
                "consumer": consumers[1], 
                "status": OrderStatus.SHIPPING,   # Existing enum
                "days_ago": 1
            }
        ]
        
        orders = []
        for order_data in orders_data:
            product = order_data["product"]
            consumer = order_data["consumer"]
            
            existing_order = db.query(Order).filter(
                Order.product_id == product.id,
                Order.consumer_id == consumer.id
            ).first()
            if existing_order:
                print(f"   Order for '{product.name}' already exists")
                orders.append(existing_order)
                continue
            
            order_number = f"BF{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
            discounted_price = product.price * (1 - product.discount_percentage / 100)
            created_date = datetime.now() - timedelta(days=order_data["days_ago"])
            
            order = Order(
                product_id=product.id,
                consumer_id=consumer.id,
                quantity_ordered=product.quantity,
                total_price=discounted_price,
                delivery_address="123 Test Street, Lagos",
                contact_phone="+234 800 555 6666",
                delivery_notes="Please call when you arrive",
                order_number=order_number,
                status=order_data["status"],
                estimated_delivery_date=created_date + timedelta(days=3),
                created_at=created_date
            )
            
            db.add(order)
            db.flush()
            
            # Create basic timeline
            timeline_entry = OrderTimeline(
                order_id=order.id,
                status=OrderTimelineStatus.PLACED,
                title="Order Placed",
                description="Your order has been placed successfully",
                is_completed=True,
                completed_at=created_date,
                created_at=created_date
            )
            db.add(timeline_entry)
            
            if order_data["status"] == OrderStatus.DELIVERED:
                delivered_entry = OrderTimeline(
                    order_id=order.id,
                    status=OrderTimelineStatus.DELIVERED,
                    title="Delivered",
                    description="Order successfully delivered",
                    is_completed=True,
                    completed_at=created_date + timedelta(days=2),
                    created_at=created_date + timedelta(days=2)
                )
                db.add(delivered_entry)
            
            orders.append(order)
        
        db.commit()
        print(f"Created {len(orders)} orders with timeline entries")
        
        print("\nSample data creation completed successfully!")
        print(f"Database: {settings.DATABASE_URL}")
        print("\nTest Credentials:")
        print("Farmers:")
        for farmer_data in farmers_data:
            print(f"   {farmer_data['email']} / {farmer_data['password']}")
        print("Consumers:")  
        for consumer_data in consumers_data:
            print(f"   {consumer_data['email']} / {consumer_data['password']}")
        print("\nYou can now test the Orders API!")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating sample data: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_data()
