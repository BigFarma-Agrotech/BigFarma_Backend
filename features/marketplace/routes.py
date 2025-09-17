from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from features.marketplace.schemas import (
    ProductCreate, ProductResponse, ProductUpdate, ProductDetailResponse,
    ProductPublicResponse, OrderCreate, OrderResponse,
    ReviewCreate, ReviewResponse
)
from features.marketplace.service import MarketplaceService
from features.auth.models import User
from features.users.models import FarmerProfile
from core.dependencies import get_current_active_user

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

# Public endpoints
@router.get("/products", response_model=List[ProductPublicResponse])
async def get_all_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = MarketplaceService(db)
    products = service.get_all_products(skip, limit)
    
    # Convert to simplified public response
    public_products = []
    for product in products:
        # Get farmer profile for farm name and farmer name
        farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
        
        # Parse images from string to list
        images = product.images.split(',') if product.images else []
        
        public_products.append(ProductPublicResponse(
            id=product.id,
            name=product.name,
            category=product.category,
            description=product.description,
            quantity=product.quantity,
            price=product.price,
            discount_percentage=product.discount_percentage,
            discounted_price=product.price * (1 - product.discount_percentage / 100),
            location=product.location,
            images=images,
            availability=product.availability,
            farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
            farmer_name=farmer_profile.full_name if farmer_profile else "Farmer"
        ))
    
    return public_products

@router.get("/products/{product_id}", response_model=ProductDetailResponse)
async def get_product_detail(product_id: int, db: Session = Depends(get_db)):
    service = MarketplaceService(db)
    product = service.get_product(product_id)
    if not product or not product.is_approved or not product.is_listed:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get farmer info from farmer profile
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
    if not farmer_profile:
        raise HTTPException(status_code=404, detail="Farmer profile not found")
    
    farmer = product.farmer
    
    return ProductDetailResponse(
        **product.__dict__,
        farmer={
            "id": farmer.id,
            "full_name": farmer_profile.full_name,
            "profile_picture": farmer_profile.profile_picture,
            "farm_name": farmer_profile.farm_name,
            "farm_location": farmer_profile.farm_location,
            "farm_type": farmer_profile.farm_type.value if farmer_profile.farm_type else "Unknown"
        },
        discounted_price=product.price * (1 - product.discount_percentage / 100)
    )

# Farmer product management (uses full response)
@router.post("/farmers/products", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can create products")
    
    service = MarketplaceService(db)
    try:
        product = service.create_product(current_user.id, product_data)
        return product
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/farmers/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can update products")
    
    service = MarketplaceService(db)
    product = service.update_product(product_id, current_user.id, product_data)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.get("/farmers/products", response_model=List[ProductResponse])
async def get_my_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can view their products")
    
    service = MarketplaceService(db)
    return service.get_farmer_products(current_user.id)

@router.delete("/farmers/products/{product_id}")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can delete products")
    
    service = MarketplaceService(db)
    success = service.delete_product(product_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}

@router.post("/farmers/products/{product_id}/discount")
async def add_discount(
    product_id: int,
    discount_percentage: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can add discounts")
    
    service = MarketplaceService(db)
    product = service.add_discount(product_id, current_user.id, discount_percentage)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.delete("/farmers/products/{product_id}/discount")
async def remove_discount(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can remove discounts")
    
    service = MarketplaceService(db)
    product = service.remove_discount(product_id, current_user.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# Order management (available to all users)
@router.post("/orders", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = MarketplaceService(db)
    order = service.create_order(current_user.id, order_data)
    if not order:
        raise HTTPException(status_code=400, detail="Could not create order")
    return order



# Review management (available to all users)
@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = MarketplaceService(db)
    review = service.create_review(current_user.id, review_data)
    if not review:
        raise HTTPException(status_code=400, detail="Could not create review")
    return review

@router.get("/products/{product_id}/reviews", response_model=List[ReviewResponse])
async def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    service = MarketplaceService(db)
    return service.get_product_reviews(product_id)