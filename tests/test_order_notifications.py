import pytest
from fastapi import BackgroundTasks
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
from features.notifications.models import Notification
# Imported for their side effect: registers every model the User mapper refers to
from features.orders.service import OrderService  # noqa: F401
from features.notifications.service import NotificationService
from services.email_service import email_service


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
    user = User(email=email, password="hashed", category=category, is_verified=True, is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture()
def order_setup(db_session):
    farmer = create_user(db_session, "farmer@example.com", UserCategory.FARMER)
    consumer = create_user(db_session, "consumer@example.com", UserCategory.CONSUMER)
    product = Product(
        farmer_id=farmer.id,
        name="Cabbage",
        category=ProductCategory.CROP,
        description="Fresh cabbage",
        quantity="30 kg",
        price=1200.0,
        location="Ibadan",
        images="",
        availability=AvailabilityStatus.IN_STOCK,
    )
    db_session.add(product)
    db_session.commit()
    order = Order(
        product_id=product.id,
        consumer_id=consumer.id,
        quantity_ordered="2",
        total_price=2400.0,
        delivery_address="12 Farm Rd, Ibadan",
        status=OrderStatus.PENDING,
        order_number="BF20261024TEST01",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return farmer, consumer, order


def notifications_for(session, user):
    return session.query(Notification).filter(Notification.user_id == user.id).all()


def queued(background_tasks, func):
    return [t for t in background_tasks.tasks if t.func == func]


def test_order_placed_notifies_buyer_and_farmer(db_session, order_setup):
    farmer, consumer, order = order_setup
    tasks = BackgroundTasks()

    NotificationService(db_session).notify_order_placed(consumer, order, tasks)

    buyer_notes = notifications_for(db_session, consumer)
    farmer_notes = notifications_for(db_session, farmer)
    assert [n.notification_type for n in buyer_notes] == ["order_placed"]
    assert [n.notification_type for n in farmer_notes] == ["new_order"]
    assert farmer_notes[0].reference_id == order.id
    assert "Cabbage" in farmer_notes[0].message

    # One email each: confirmation to the buyer, new-order alert to the farmer
    assert queued(tasks, email_service.send_order_confirmation_email)[0].kwargs["to_email"] == consumer.email
    assert queued(tasks, email_service.send_new_order_email)[0].kwargs["to_email"] == farmer.email


def test_status_change_notifies_buyer(db_session, order_setup):
    farmer, consumer, order = order_setup
    order.status = OrderStatus.SHIPPING
    db_session.commit()

    NotificationService(db_session).notify_order_status_changed(order, BackgroundTasks())

    notes = notifications_for(db_session, consumer)
    assert [(n.notification_type, n.title) for n in notes] == [("order_status", "Order on its way")]
    assert notifications_for(db_session, farmer) == []


def test_pending_status_sends_nothing(db_session, order_setup):
    _, consumer, order = order_setup
    NotificationService(db_session).notify_order_status_changed(order, BackgroundTasks())
    assert notifications_for(db_session, consumer) == []


def test_delivery_confirmed_and_issue_notify_farmer(db_session, order_setup):
    farmer, _, order = order_setup
    service = NotificationService(db_session)

    service.notify_delivery_confirmed(order, BackgroundTasks())
    service.notify_delivery_issue(order, BackgroundTasks())

    notes = notifications_for(db_session, farmer)
    assert [n.notification_type for n in notes] == ["delivery_confirmed", "delivery_issue"]
    assert "₦2,400.00" in notes[0].message


def test_new_order_email_renders(order_setup):
    html = email_service._render_template(
        "new_order.html",
        name="Ada",
        order_number="BF1",
        product_name="Cabbage",
        quantity="2",
        total_price="2,400.00",
        delivery_address="12 Farm Rd",
        estimated_delivery=None,
    )
    assert "You Have a New Order" in html and "Cabbage" in html
