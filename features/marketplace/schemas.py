from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ProductCategory(str, Enum):
    VEGETABLES = "vegetables"
    FRUITS = "fruits"
    GRAINS = "grains"
    PROTEINS = "proteins"
    CROP = "crop"
    LIVESTOCK = "livestock"

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

class ProductCreate(ProductBase):
    pass

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
    farmer_id: int
    is_approved: bool
    is_listed: bool
    availability: AvailabilityStatus
    total_ratings: int
    average_rating: float
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

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
    farm_name: str
    farmer_name: str

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