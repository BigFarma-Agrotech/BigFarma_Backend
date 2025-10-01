"""
Sample data generator for BigFarma Backend including wallet seed data.
Run this script to populate the database with test users, products, and wallet activity.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
import uuid

# Ensure project root on path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from database import SessionLocal, engine, Base
from config import settings

from features.auth.models import User, UserCategory
from features.users.models import FarmerProfile, ConsumerProfile, FarmType
from features.marketplace.models import (
    Product,
    Order,
    Review,
    ProductCategory,
    AvailabilityStatus,
    OrderStatus,
)
from features.orders.models import (
    OrderTimeline,
    OrderIssue,
    OrderTimelineStatus,
    IssueStatus,
)
from features.wallet.services import WalletService, BankVerificationService, WithdrawalService
from features.wallet.models import TransactionCategory
from features.wallet.schemas import (
    BankAccountCreateRequest,
    BankAccountVerifyResponse,
    WithdrawalRequestCreate,
)
from features.wallet.exceptions import DuplicateBankAccountError
from core.security import get_password_hash


def create_sample_data():
    """Create comprehensive sample data for testing."""

    print(f"Using database: {settings.DATABASE_URL}")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        if db.query(User).count() > 0:
            response = input("Database already contains users. Continue anyway? (y/n): ").strip().lower()
            if response != "y":
                print("Cancelled")
                return

        print("Creating sample farmers...")
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
                    "years_experience": 10,
                },
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
                    "years_experience": 15,
                },
            },
        ]

        farmers = []
        for data in farmers_data:
            user = db.query(User).filter(User.email == data["email"]).first()
            if user:
                print(f"   Farmer {data['email']} already exists")
                farmers.append(user)
                continue

            user = User(
                email=data["email"],
                phone_number=data["phone"],
                password=get_password_hash(data["password"]),
                category=UserCategory.FARMER,
                is_verified=True,
            )
            db.add(user)
            db.flush()

            profile = FarmerProfile(
                user_id=user.id,
                full_name=data["profile"]["full_name"],
                home_address=data["profile"]["home_address"],
                id_document=data["profile"]["id_document"],
                farm_name=data["profile"]["farm_name"],
                farm_location=data["profile"]["farm_location"],
                farm_type=data["profile"]["farm_type"],
                farm_size=data["profile"]["farm_size"],
                years_experience=data["profile"]["years_experience"],
                is_verified=True,
            )
            db.add(profile)
            farmers.append(user)

        print("Creating sample consumers...")
        consumers_data = [
            {
                "email": "jane.consumer@bigfarma.com",
                "phone": "+234-800-555-1001",
                "password": "consumer123",
                "profile": {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "address": "Victoria Island, Lagos",
                },
            },
            {
                "email": "ahmed.buyer@bigfarma.com",
                "phone": "+234-800-555-1002",
                "password": "consumer123",
                "profile": {
                    "first_name": "Ahmed",
                    "last_name": "Musa",
                    "address": "Garki, Abuja",
                },
            },
        ]

        consumers = []
        for data in consumers_data:
            user = db.query(User).filter(User.email == data["email"]).first()
            if user:
                print(f"   Consumer {data['email']} already exists")
                consumers.append(user)
                continue

            user = User(
                email=data["email"],
                phone_number=data["phone"],
                password=get_password_hash(data["password"]),
                category=UserCategory.CONSUMER,
                is_verified=True,
            )
            db.add(user)
            db.flush()

            profile = ConsumerProfile(
                user_id=user.id,
                first_name=data["profile"]["first_name"],
                last_name=data["profile"]["last_name"],
                address=data["profile"]["address"],
            )
            db.add(profile)
            consumers.append(user)

        db.commit()
        print(f"Created/confirmed {len(farmers)} farmers and {len(consumers)} consumers")

        print("Creating sample products...")
        products_data = [
            {
                "farmer_id": farmers[0].id,
                "name": "Organic Tomatoes",
                "category": ProductCategory.CROP,
                "description": "Fresh organic tomatoes grown without chemicals.",
                "quantity": 100,
                "price": 1500.0,
                "discount_percentage": 10.0,
                "location": "Ikeja, Lagos",
                "images": ["https://example.com/tomatoes.jpg"],
            },
            {
                "farmer_id": farmers[1].id,
                "name": "Free-range Eggs",
                "category": ProductCategory.LIVESTOCK,
                "description": "Eggs from free-range chickens.",
                "quantity": 200,
                "price": 2500.0,
                "discount_percentage": 5.0,
                "location": "Garki, Abuja",
                "images": ["https://example.com/eggs.jpg"],
            },
        ]

        products = []
        for data in products_data:
            product = db.query(Product).filter(Product.name == data["name"]).first()
            if product:
                print(f"   Product '{data['name']}' already exists")
                products.append(product)
                continue

            product = Product(
                farmer_id=data["farmer_id"],
                name=data["name"],
                category=data["category"],
                description=data["description"],
                quantity=data["quantity"],
                price=data["price"],
                discount_percentage=data["discount_percentage"],
                location=data["location"],
                images=data["images"],
                is_approved=True,
                is_listed=True,
                availability=AvailabilityStatus.IN_STOCK,
            )
            db.add(product)
            products.append(product)

        db.commit()
        print(f"Created/confirmed {len(products)} products")

        print("Creating sample orders...")
        orders_data = [
            {
                "product": products[0],
                "consumer": consumers[0],
                "status": OrderStatus.DELIVERED,
                "days_ago": 5,
            },
            {
                "product": products[1],
                "consumer": consumers[1],
                "status": OrderStatus.SHIPPING,
                "days_ago": 1,
            },
        ]

        orders = []
        for data in orders_data:
            product = data["product"]
            consumer = data["consumer"]
            order = db.query(Order).filter(
                Order.product_id == product.id,
                Order.consumer_id == consumer.id,
            ).first()
            if order:
                print(f"   Order for '{product.name}' already exists")
                orders.append(order)
                continue

            created_date = datetime.now(timezone.utc) - timedelta(days=data["days_ago"])
            order_number = f"BF{created_date.strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
            discounted_price = product.price * (1 - product.discount_percentage / 100)

            order = Order(
                product_id=product.id,
                consumer_id=consumer.id,
                quantity_ordered=product.quantity,
                total_price=discounted_price,
                delivery_address="123 Test Street, Lagos",
                contact_phone="+234 800 555 6666",
                delivery_notes="Please call when you arrive",
                order_number=order_number,
                status=data["status"],
                estimated_delivery_date=created_date + timedelta(days=3),
                created_at=created_date,
            )
            db.add(order)
            db.flush()

            timeline = OrderTimeline(
                order_id=order.id,
                status=OrderTimelineStatus.PLACED,
                title="Order Placed",
                description="Your order has been placed successfully",
                is_completed=True,
                completed_at=created_date,
                created_at=created_date,
            )
            db.add(timeline)

            if data["status"] == OrderStatus.DELIVERED:
                delivered = OrderTimeline(
                    order_id=order.id,
                    status=OrderTimelineStatus.DELIVERED,
                    title="Delivered",
                    description="Order successfully delivered",
                    is_completed=True,
                    completed_at=created_date + timedelta(days=2),
                    created_at=created_date + timedelta(days=2),
                )
                db.add(delivered)

            orders.append(order)

        db.commit()
        print(f"Created/confirmed {len(orders)} orders")

        # ------------------------------------------------------------------
        # Wallet seed data
        # ------------------------------------------------------------------
        print("Seeding wallet data...")
        wallet_service = WalletService(db)
        bank_service = BankVerificationService(db)
        withdrawal_service = WithdrawalService(db, wallet_service)

        wallet_seed = [
            {
                "farmer": farmers[0],
                "credits": [
                    (1500.0, TransactionCategory.PRODUCT_SALE, "Bulk tomato sale"),
                    (350.0, TransactionCategory.BONUS, "Loyalty bonus"),
                ],
                "bank_accounts": [
                    {
                        "account_number": "1234567890",
                        "bank_code": "058",
                        "bank_name": "Guaranty Trust Bank",
                    },
                    {
                        "account_number": "5555666677",
                        "bank_code": "057",
                        "bank_name": "Zenith Bank",
                    },
                ],
                "withdrawal": 600.0,
            },
            {
                "farmer": farmers[1],
                "credits": [
                    (2500.0, TransactionCategory.PRODUCT_SALE, "Egg shipment"),
                    (500.0, TransactionCategory.DEPOSIT, "Investor top-up"),
                ],
                "bank_accounts": [
                    {
                        "account_number": "0987654321",
                        "bank_code": "033",
                        "bank_name": "United Bank for Africa",
                    }
                ],
                "withdrawal": 900.0,
            },
        ]

        for seed in wallet_seed:
            farmer = seed["farmer"]
            wallet = wallet_service.create_wallet(farmer.id)

            for amount, category, description in seed["credits"]:
                wallet_service.credit_wallet(
                    wallet_id=wallet.id,
                    amount=amount,
                    category=category,
                    description=description,
                )

            primary_account = None
            for idx, acct in enumerate(seed["bank_accounts"]):
                request = BankAccountCreateRequest(
                    account_number=acct["account_number"],
                    bank_code=acct["bank_code"],
                )
                verification = BankAccountVerifyResponse(
                    account_number=acct["account_number"],
                    account_name=farmer.farmer_profile.full_name if farmer.farmer_profile else "BIGFARMA USER",
                    bank_code=acct["bank_code"],
                    bank_name=acct["bank_name"],
                    is_valid=True,
                    recipient_code=f"RCP_{acct['account_number']}",
                )
                try:
                    bank_account = bank_service.add_bank_account(farmer.id, request, verification)
                except DuplicateBankAccountError:
                    bank_account = bank_service.get_bank_accounts(farmer.id)[idx]

                if idx == 0:
                    primary_account = bank_account

            if primary_account is None:
                accounts = bank_service.get_bank_accounts(farmer.id)
                primary_account = accounts[0] if accounts else None

            if primary_account and seed.get("withdrawal"):
                amount = seed["withdrawal"]
                request = WithdrawalRequestCreate(
                    amount=amount,
                    bank_account_id=primary_account.id,
                    idempotency_key=f"seed-withdraw-{farmer.id}",
                )
                withdrawal_service.create_withdrawal_request(farmer.id, request)

        db.commit()
        print("Wallet data seeded for each farmer")

        print("\nSample data creation completed successfully!\n")
        print("Credentials:")
        for farmer in farmers_data:
            print(f"  Farmer: {farmer['email']} / {farmer['password']}")
        for consumer in consumers_data:
            print(f"  Consumer: {consumer['email']} / {consumer['password']}")
        print("\nWallet balances are ready for withdrawal testing.")

    except Exception as exc:
        db.rollback()
        print(f"Error creating sample data: {exc}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_sample_data()


