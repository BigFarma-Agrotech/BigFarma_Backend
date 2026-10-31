from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CheckoutItem(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)


class CheckoutRequest(BaseModel):
    items: List[CheckoutItem] = Field(..., min_length=1)
    delivery_address: str
    contact_name: str
    contact_phone: str
    delivery_option: Literal["door-delivery", "pickup"] = "door-delivery"
    # Receipt email for Paystack; the account's email is used when left out
    email: Optional[str] = None
    # Where Paystack sends the buyer after paying (must be one of our sites)
    callback_url: str

    @field_validator("delivery_address", "contact_name", "contact_phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("This field is required")
        return v.strip()

    @field_validator("email")
    @classmethod
    def blank_email_is_none(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v and v.strip() else None


class PaymentOrder(BaseModel):
    public_id: str
    order_number: str
    product_name: str
    quantity_ordered: str
    total_price: float


class PaymentResponse(BaseModel):
    reference: str
    status: str  # pending | success | failed | abandoned
    subtotal: float
    delivery_fee: float
    tax: float
    amount: float
    paid_at: Optional[datetime] = None
    gateway_response: Optional[str] = None
    orders: List[PaymentOrder] = []


class CheckoutResponse(PaymentResponse):
    authorization_url: str
