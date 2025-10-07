import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from features.auth.models import User, UserCategory
from features.marketplace.models import (
    Product,
    Order,
    ProductCategory,
    AvailabilityStatus,
    OrderStatus,
)
from features.orders.service import OrderService
from features.wallet.services import WalletService


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def create_user(session, email: str, category: UserCategory) -> User:
    user = User(
        email=email,
        password="hashed",
        category=category,
        is_verified=True,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_confirm_delivery_credits_wallet(db_session):
    farmer = create_user(db_session, "farmer@example.com", UserCategory.FARMER)
    consumer = create_user(db_session, "consumer@example.com", UserCategory.CONSUMER)

    product = Product(
        farmer_id=farmer.id,
        name="Fresh Tomatoes",
        category=ProductCategory.CROP,
        description="Organic tomatoes",
        quantity="50 crates",
        price=2000.0,
        discount_percentage=0.0,
        location="Lagos",
        images="https://example.com/tomatoes.jpg",
        is_approved=True,
        is_listed=True,
        availability=AvailabilityStatus.IN_STOCK,
    )
    db_session.add(product)
    db_session.commit()

    order = Order(
        product_id=product.id,
        consumer_id=consumer.id,
        quantity_ordered="5",
        total_price=2000.0,
        delivery_address="123 Sample Street",
        status=OrderStatus.AWAITING_CONFIRMATION,
    )
    db_session.add(order)
    db_session.commit()

    service = OrderService(db_session)
    updated_order = service.confirm_delivery(order.id, consumer.id)

    assert updated_order is not None
    assert updated_order.status == OrderStatus.DELIVERED

    wallet_service = WalletService(db_session)
    wallet = wallet_service.get_wallet_by_farmer_id(farmer.id)
    assert wallet.balance == pytest.approx(2000.0)
    assert wallet.ledger_balance == pytest.approx(2000.0)
    assert wallet.transactions[0].description == "Sale of Fresh Tomatoes"
