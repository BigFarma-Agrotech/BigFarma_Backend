from pydantic import BaseModel, validator
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

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Product name is required')
        return v.strip()

    @validator('description')
    def description_must_be_min_length(cls, v):
        if not v or len(v.strip()) < 20:
            raise ValueError('Description must be at least 20 characters long')
        return v.strip()

    @validator('price')
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        return v

    @validator('discount_percentage')
    def discount_must_be_valid(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Discount percentage must be between 0 and 100')
        return v

    @validator('images')
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

    @validator('name', 'description')
    def validate_string_fields(cls, v, field):
        if v is not None and not v.strip():
            raise ValueError(f'{field.name} cannot be empty')
        return v.strip() if v else v

    @validator('price')
    def validate_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Price must be greater than 0')
        return v

    @validator('discount_percentage')
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

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    product_id: int
    quantity_ordered: str
    delivery_address: str

    @validator('delivery_address')
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

    class Config:
        from_attributes = True

class OrderDetailResponse(OrderResponse):
    product_name: str
    farm_name: str
    farmer_name: str

    class Config:
        from_attributes = True

class ReviewBase(BaseModel):
    product_id: int
    rating: int
    comment: Optional[str] = None

    @validator('rating')
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v

    @validator('comment')
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

    class Config:
        from_attributes = True

class ProductSearchResponse(BaseModel):
    products: List[ProductPublicResponse]
    total_count: int
    page: int
    page_size: int
    search_suggestions: List[str] = []
    filter_suggestions: List[str] = []
    related_products: List[dict] = []
    filters_applied: bool = False

class ProductFilterRequest(BaseModel):
    categories: Optional[List[ProductCategory]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    locations: Optional[List[str]] = None
    availability: Optional[str] = None

    class Config:
        from_attributes = True