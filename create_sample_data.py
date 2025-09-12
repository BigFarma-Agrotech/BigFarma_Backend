"""
Sample data generator for BigFarma Backend
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
    
    # Create tables using the existing database configuration
    print(f"Using database: {settings.DATABASE_URL}")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"⚠️  Database already has {existing_users} users. Do you want to continue? (y/n)")
            response = input().lower().strip()
            if response != 'y':
                print("❌ Cancelled - No changes made to database")
                return
            
        # Create sample users
        print("Creating sample users...")
        
        # Sample Farmers
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
            },
            {
                "email": "ibrahim.dan@bigfarma.com",
                "phone": "+234-800-555-0003", 
                "password": "farmer123",
                "profile": {
                    "full_name": "Ibrahim Dan",
                    "home_address": "45 Dan Road, Kano, Kano State",
                    "id_document": "https://example.com/id_ibrahim.jpg",
                    "farm_name": "Dan Farm",
                    "farm_location": "Kano, Kano State",
                    "farm_type": FarmType.LIVESTOCK,
                    "farm_size": "20 acres",
                    "years_experience": 8
                }
            },
            {
                "email": "sunny.coop@bigfarma.com",
                "phone": "+234-800-555-0004",
                "password": "farmer123", 
                "profile": {
                    "full_name": "Sunny Cooperative",
                    "home_address": "12 Cooperative Lane, Abeokuta, Ogun State",
                    "id_document": "https://example.com/id_sunny.jpg",
                    "farm_name": "SunnyCoop",
                    "farm_location": "Ogun State",
                    "farm_type": FarmType.MIXED,
                    "farm_size": "3 acres",
                    "years_experience": 5
                }
            }
        ]
        
        farmers = []
        for farmer_data in farmers_data:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == farmer_data["email"]).first()
            if existing_user:
                print(f"   Farmer {farmer_data['email']} already exists, skipping...")
                farmers.append(existing_user)
                continue
                
            # Create user
            user = User(
                email=farmer_data["email"],
                phone_number=farmer_data["phone"],
                password=get_password_hash(farmer_data["password"]),
                category=UserCategory.FARMER,
                is_verified=True
            )
            db.add(user)
            db.flush()
            
            # Create farmer profile
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
        
        # Sample Consumers
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
            },
            {
                "email": "grace.okoro@bigfarma.com",
                "phone": "+234-800-555-1003",
                "password": "consumer123",
                "profile": {
                    "first_name": "Grace",
                    "last_name": "Okoro",
                    "address": "Port Harcourt, Rivers"
                }
            }
        ]
        
        consumers = []
        for consumer_data in consumers_data:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == consumer_data["email"]).first()
            if existing_user:
                print(f"   Consumer {consumer_data['email']} already exists, skipping...")
                consumers.append(existing_user)
                continue
                
            # Create user
            user = User(
                email=consumer_data["email"],
                phone_number=consumer_data["phone"],
                password=get_password_hash(consumer_data["password"]),
                category=UserCategory.CONSUMER,
                is_verified=True
            )
            db.add(user)
            db.flush()
            
            # Create consumer profile
            profile = ConsumerProfile(
                user_id=user.id,
                first_name=consumer_data["profile"]["first_name"],
                last_name=consumer_data["profile"]["last_name"],
                address=consumer_data["profile"]["address"]
            )
            db.add(profile)
            consumers.append(user)
        
        db.commit()
        print(f"✅ Created/verified {len(farmers)} farmers and {len(consumers)} consumers")
        
        # Create sample products
        print("Creating sample products...")
        products_data = [
            {
                "farmer_id": farmers[0].id,  # GreenRoots Farm
                "name": "Fresh Tomatoes (Basket)",
                "category": ProductCategory.CROP,
                "description": "Fresh, red tomatoes harvested this morning",
                "quantity": "1 basket (25kg)",
                "price": 5000.0,
                "discount_percentage": 0.0,
                "location": "Ikeja, Lagos",
                "images": "https://example.com/tomato1.jpg,https://example.com/tomato2.jpg"
            },
            {
                "farmer_id": farmers[0].id,
                "name": "Fresh Peppers (Basket)",
                "category": ProductCategory.CROP,
                "description": "Spicy red peppers, perfect for cooking",
                "quantity": "1 basket (15kg)",
                "price": 8000.0,
                "discount_percentage": 15.0,
                "location": "Ikeja, Lagos",
                "images": "https://example.com/pepper1.jpg,https://example.com/pepper2.jpg"
            },
            {
                "farmer_id": farmers[1].id,  # Adaku Farm
                "name": "Watermelon (5 Pcs)",
                "category": ProductCategory.CROP,
                "description": "Sweet, juicy watermelons",
                "quantity": "5 pieces",
                "price": 12000.0,
                "discount_percentage": 0.0,
                "location": "Abuja, FCT",
                "images": "https://example.com/watermelon1.jpg"
            },
            {
                "farmer_id": farmers[1].id,
                "name": "Potatoes (5kg)",
                "category": ProductCategory.CROP,
                "description": "Fresh potatoes perfect for cooking",
                "quantity": "5kg bag",
                "price": 3500.0,
                "discount_percentage": 0.0,
                "location": "Abuja, FCT", 
                "images": "https://example.com/potato1.jpg"
            },
            {
                "farmer_id": farmers[3].id,  # SunnyCoop
                "name": "Eggs (30 Crates)",
                "category": ProductCategory.LIVESTOCK,
                "description": "Fresh eggs from free-range chickens",
                "quantity": "30 crates",
                "price": 45000.0,
                "discount_percentage": 5.0,
                "location": "Ogun State",
                "images": "https://example.com/eggs1.jpg,https://example.com/eggs2.jpg"
            }
        ]
        
        products = []
        for product_data in products_data:
            # Check if product already exists
            existing_product = db.query(Product).filter(
                Product.farmer_id == product_data["farmer_id"],
                Product.name == product_data["name"]
            ).first()
            if existing_product:
                print(f"   Product '{product_data['name']}' already exists, skipping...")
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
        print(f"✅ Created/verified {len(products)} products")
        
        # Create sample orders with different statuses
        print("Creating sample orders...")
        orders_data = [
            {
                "product": products[0],  # Fresh Tomatoes
                "consumer": consumers[0],  # Jane Smith
                "status": OrderStatus.DELIVERED,
                "days_ago": 5
            },
            {
                "product": products[1],  # Fresh Peppers  
                "consumer": consumers[0],
                "status": OrderStatus.AWAITING_CONFIRMATION,
                "days_ago": 1
            },
            {
                "product": products[2],  # Watermelon
                "consumer": consumers[1],  # Ahmed Musa
                "status": OrderStatus.SHIPPING,
                "days_ago": 2
            },
            {
                "product": products[3],  # Potatoes
                "consumer": consumers[2],  # Grace Okoro
                "status": OrderStatus.DELIVERY_ISSUE,
                "days_ago": 3
            },
            {
                "product": products[4],  # Eggs
                "consumer": consumers[1],
                "status": OrderStatus.PENDING,
                "days_ago": 0
            }
        ]
        
        orders = []
        for i, order_data in enumerate(orders_data):
            product = order_data["product"]
            consumer = order_data["consumer"]
            
            # Check if order already exists
            existing_order = db.query(Order).filter(
                Order.product_id == product.id,
                Order.consumer_id == consumer.id
            ).first()
            if existing_order:
                print(f"   Order for '{product.name}' by consumer {consumer.id} already exists, skipping...")
                orders.append(existing_order)
                continue
            
            # Generate order number
            order_number = f"BF{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
            
            # Calculate price with discount
            discounted_price = product.price * (1 - product.discount_percentage / 100)
            
            # Set dates
            created_date = datetime.now() - timedelta(days=order_data["days_ago"])
            estimated_delivery = created_date + timedelta(days=3)
            
            order = Order(
                product_id=product.id,
                consumer_id=consumer.id,
                quantity_ordered=product.quantity,
                total_price=discounted_price,
                delivery_address="123 example street, Ikeja, Lagos",
                contact_phone="+234 800 555 6666",
                delivery_notes="Please call when you arrive",
                order_number=order_number,
                status=order_data["status"],
                estimated_delivery_date=estimated_delivery,
                created_at=created_date
            )
            db.add(order)
            db.flush()
            
            # Create timeline entries based on status
            timeline_entries = []
            
            # Always have "Placed" entry
            timeline_entries.append({
                "status": OrderTimelineStatus.PLACED,
                "title": "Order Placed",
                "description": "Your order has been placed successfully",
                "is_completed": True,
                "created_at": created_date
            })
            
            if order_data["status"] in [OrderStatus.SHIPPING, OrderStatus.AWAITING_CONFIRMATION, OrderStatus.DELIVERED]:
                timeline_entries.append({
                    "status": OrderTimelineStatus.SHIPPING_IN_PROGRESS,
                    "title": "Shipping In Progress", 
                    "description": "Your order is on its way",
                    "is_completed": True,
                    "created_at": created_date + timedelta(hours=6)
                })
            
            if order_data["status"] in [OrderStatus.AWAITING_CONFIRMATION, OrderStatus.DELIVERED]:
                timeline_entries.append({
                    "status": OrderTimelineStatus.DELIVERED_TO_CUSTOMER,
                    "title": "Delivered To Customer",
                    "description": "Handed off the order",
                    "is_completed": True,
                    "created_at": created_date + timedelta(days=1)
                })
                
                timeline_entries.append({
                    "status": OrderTimelineStatus.AWAITING_CONFIRMATION,
                    "title": "Awaiting Confirmation",
                    "description": "Waiting for your confirmation",
                    "is_completed": order_data["status"] == OrderStatus.DELIVERED,
                    "created_at": created_date + timedelta(days=1, hours=1)
                })
            
            if order_data["status"] == OrderStatus.DELIVERED:
                timeline_entries.append({
                    "status": OrderTimelineStatus.DELIVERED,
                    "title": "Delivered", 
                    "description": "Order successfully delivered and confirmed",
                    "is_completed": True,
                    "created_at": created_date + timedelta(days=2)
                })
            
            # Create timeline entries
            for timeline_data in timeline_entries:
                timeline_entry = OrderTimeline(
                    order_id=order.id,
                    status=timeline_data["status"],
                    title=timeline_data["title"],
                    description=timeline_data["description"],
                    is_completed=timeline_data["is_completed"],
                    completed_at=timeline_data["created_at"] if timeline_data["is_completed"] else None,
                    created_at=timeline_data["created_at"]
                )
                db.add(timeline_entry)
            
            orders.append(order)
        
        # Create a delivery issue for the DELIVERY_ISSUE order (if not exists)
        issue_orders = [o for o in orders if o.status == OrderStatus.DELIVERY_ISSUE]
        if issue_orders:
            issue_order = issue_orders[0]
            existing_issue = db.query(OrderIssue).filter(OrderIssue.order_id == issue_order.id).first()
            if not existing_issue:
                issue = OrderIssue(
                    order_id=issue_order.id,
                    consumer_id=issue_order.consumer_id,
                    issue_description="Package left at gate, items missing, never received, etc.",
                    status=IssueStatus.REPORTED,
                    created_at=datetime.now() - timedelta(days=2)
                )
                db.add(issue)
        
        db.commit()
        print(f"✅ Created/verified {len(orders)} orders with timeline entries and delivery issues")
        
        # Create sample reviews (if not exists)
        print("Creating sample reviews...")
        delivered_orders = [o for o in orders if o.status == OrderStatus.DELIVERED]
        reviews_created = 0
        
        for order in delivered_orders:
            existing_review = db.query(Review).filter(
                Review.product_id == order.product_id,
                Review.consumer_id == order.consumer_id
            ).first()
            if existing_review:
                continue
                
            review = Review(
                product_id=order.product_id,
                consumer_id=order.consumer_id,
                rating=5,
                comment="Excellent quality! Fresh and delivered on time. Highly recommend!",
                created_at=datetime.now() - timedelta(days=1)
            )
            db.add(review)
            
            # Update product ratings
            product = order.product
            product.total_ratings += 1
            product.average_rating = 5.0  # Simplified for demo
            reviews_created += 1
        
        db.commit()
        print(f"✅ Created {reviews_created} reviews")
        
        print("\n🎉 Sample data creation completed successfully!")
        print(f"📊 Database: {settings.DATABASE_URL}")
        print("\n📝 Test Credentials:")
        print("\n🧑‍🌾 Farmers:")
        for farmer_data in farmers_data:
            print(f"   Email: {farmer_data['email']}")
            print(f"   Password: {farmer_data['password']}")
            print(f"   Farm: {farmer_data['profile']['farm_name']}")
            print()
        
        print("\n🛒 Consumers:")
        for consumer_data in consumers_data:
            print(f"   Email: {consumer_data['email']}")
            print(f"   Password: {consumer_data['password']}")
            print(f"   Name: {consumer_data['profile']['first_name']} {consumer_data['profile']['last_name']}")
            print()
        
        print("🚀 You can now test the Orders API with these accounts!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating sample data: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_data()
