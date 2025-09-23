from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from features.marketplace.models import ProductCategory, AvailabilityStatus, OrderStatus

class ProductBase(BaseModel):
    name: str
    category: ProductCategory
    description: Optional[str] = None
    quantity: str
    price: float
    discount_percentage: float = 0.0
    location: str
    images: List[str]  # List of image URLs

    @validator('images', pre=True)
    def convert_images_to_list(cls, v):
        if isinstance(v, str):
            # Convert comma-separated string to list
            if v.strip():
                return [img.strip() for img in v.split(',')]
            else:
                return []
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

    @validator('images', pre=True)
    def convert_images_to_list(cls, v):
        if isinstance(v, str):
            if v.strip():
                return [img.strip() for img in v.split(',')]
            else:
                return []
        return v

# Simplified response for public endpoint
class ProductPublicResponse(BaseModel):
    id: int
    name: str
    category: ProductCategory
    description: Optional[str] = None
    quantity: str
    price: float
    discount_percentage: float = 0.0
    discounted_price: float
    location: str
    images: List[str]
    availability: AvailabilityStatus
    farm_name: str
    farmer_name: str

    @validator('images', pre=True)
    def convert_images_to_list(cls, v):
        if isinstance(v, str):
            if v.strip():
                return [img.strip() for img in v.split(',')]
            else:
                return []
        return v
    
    class Config:
        from_attributes = True

# Full response for farmers (includes all fields)
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

class OrderBase(BaseModel):
    product_id: int
    quantity_ordered: str
    delivery_address: str

class OrderCreate(OrderBase):
    pass

class OrderResponse(OrderBase):
    id: int
    consumer_id: int
    total_price: float
    status: OrderStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class OrderDetailResponse(OrderResponse):
    product_name: str
    farm_name: str
    farmer_name: str

class ReviewBase(BaseModel):
    rating: int
    comment: Optional[str] = None

    @validator('rating')
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v

class ReviewCreate(ReviewBase):
    product_id: int

class ReviewResponse(ReviewBase):
    id: int
    product_id: int
    consumer_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# New schemas for search and filtering
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
    farm_types: Optional[List[str]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    locations: Optional[List[str]] = None
    crop_types: Optional[List[str]] = None
    
    class Config:
        from_attributes = True