from pydantic import BaseModel, field_validator, ConfigDict, model_validator
from typing import Optional, List, Dict

from utils.units import is_count_unit, normalize_unit, parse_quantity
from datetime import datetime
from enum import Enum

from features.marketplace.models import ProductCategory  # one list for the API and the database

class AvailabilityStatus(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class ProductBase(BaseModel):
    name: str
    category: ProductCategory
    description: str
    quantity: str
    # Sold per `unit`; buyers must order at least `min_order_quantity` of it
    unit: Optional[str] = None
    min_order_quantity: float = 1.0
    price: float
    discount_percentage: float = 0.0
    location: str
    images: List[str]

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Product name is required')
        return v.strip()

    @field_validator('description')
    @classmethod
    def description_must_be_min_length(cls, v):
        if not v or len(v.strip()) < 20:
            raise ValueError('Description must be at least 20 characters long')
        return v.strip()

    @field_validator('price')
    @classmethod
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        return v

    @field_validator('discount_percentage')
    @classmethod
    def discount_must_be_valid(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Discount percentage must be between 0 and 100')
        return v

    @field_validator('images')
    @classmethod
    def images_must_not_be_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one image is required')
        return v

def _check_order_rules(quantity, unit, min_order_quantity):
    """Shared by create/update: returns the normalized unit, or raises ValueError."""
    stock, stock_unit = parse_quantity(quantity)
    unit = normalize_unit(unit) or stock_unit
    if min_order_quantity is not None:
        if min_order_quantity <= 0:
            raise ValueError("Minimum order must be greater than 0")
        if is_count_unit(unit) and not float(min_order_quantity).is_integer():
            raise ValueError(f"Minimum order must be a whole number of {unit}")
        if stock is not None and stock > 0 and min_order_quantity > stock:
            raise ValueError("Minimum order can't be more than the quantity in stock")
    return unit


class ProductCreate(ProductBase):
    @model_validator(mode="after")
    def order_rules(self):
        # The unit defaults to the one in the quantity ("100 kg" -> "kg")
        self.unit = _check_order_rules(self.quantity, self.unit, self.min_order_quantity)
        return self

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[ProductCategory] = None
    description: Optional[str] = None
    quantity: Optional[str] = None
    price: Optional[float] = None
    discount_percentage: Optional[float] = None
    location: Optional[str] = None
    images: Optional[List[str]] = None
    is_listed: Optional[bool] = None
    unit: Optional[str] = None
    min_order_quantity: Optional[float] = None

    @model_validator(mode="after")
    def order_rules(self):
        # Checks against the stored product happen in the service; these catch
        # what can be judged from the update alone
        if self.unit is not None or self.min_order_quantity is not None:
            unit = _check_order_rules(self.quantity, self.unit, self.min_order_quantity)
            if self.unit is not None:
                self.unit = unit
        return self

    @field_validator('name', 'description')
    @classmethod
    def validate_string_fields(cls, v, info):
        if v is not None and not v.strip():
            field_name = info.field_name
            raise ValueError(f'{field_name} cannot be empty')
        return v.strip() if v else v

    @field_validator('price')
    @classmethod
    def validate_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Price must be greater than 0')
        return v

    @field_validator('discount_percentage')
    @classmethod
    def validate_discount(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Discount percentage must be between 0 and 100')
        return v

class ProductResponse(ProductBase):
    id: int
    public_id: str
    farmer_id: int
    is_approved: bool
    is_listed: bool
    availability: AvailabilityStatus
    total_ratings: int
    average_rating: float
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class FarmerProductResponse(ProductResponse):
    # Orders placed for this product, for the farmer's orders table
    order_count: int = 0
    # The same orders by status, e.g. {"pending": 2, "delivered": 1}; statuses with none are left out
    order_status_counts: Dict[str, int] = {}

class FarmerInfo(BaseModel):
    id: int
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    farm_name: str
    farm_location: str
    farm_type: str

class ProductDetailResponse(ProductResponse):
    farmer: FarmerInfo
    discounted_price: float

    model_config = ConfigDict(from_attributes=True)

class ProductPublicResponse(BaseModel):
    id: int
    public_id: str
    unit: Optional[str] = None
    min_order_quantity: float = 1.0
    name: str
    category: ProductCategory
    description: str
    quantity: str
    price: float
    discount_percentage: float
    discounted_price: float
    location: str
    images: List[str]
    availability: AvailabilityStatus
    total_ratings: int
    average_rating: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    farm_name: str
    farmer_name: str
    farmer_id: int
    is_approved: bool
    is_listed: bool

    model_config = ConfigDict(from_attributes=True)

class OrderBase(BaseModel):
    product_id: int
    quantity_ordered: str
    delivery_address: str

    @field_validator('delivery_address')
    @classmethod
    def address_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Delivery address is required')
        return v.strip()

class OrderCreate(OrderBase):
    pass

class OrderResponse(OrderBase):
    id: int
    public_id: str
    product_public_id: Optional[str] = None
    consumer_id: int
    total_price: float
    status: OrderStatus
    order_number: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class OrderDetailResponse(OrderResponse):
    product_name: str
    farm_name: str
    farmer_name: str

    model_config = ConfigDict(from_attributes=True)

class ReviewBase(BaseModel):
    product_id: int
    rating: int
    comment: Optional[str] = None

    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v

    @field_validator('comment')
    @classmethod
    def validate_comment(cls, v):
        if v is not None and len(v.strip()) < 10:
            raise ValueError('Comment must be at least 10 characters long')
        return v.strip() if v else v

class ReviewCreate(ReviewBase):
    pass

class ReviewResponse(ReviewBase):
    id: int
    consumer_id: int
    created_at: datetime
    consumer_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ProductSearchResponse(BaseModel):
    products: List[ProductPublicResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool

class ProductFilterRequest(BaseModel):
    categories: Optional[List[ProductCategory]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    locations: Optional[List[str]] = None
    availability: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)