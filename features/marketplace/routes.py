from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from database import get_db
from features.marketplace.models import Product
from features.marketplace.schemas import (
    ProductCreate, ProductResponse, ProductUpdate, ProductDetailResponse,
    ProductPublicResponse, OrderCreate, OrderResponse, OrderDetailResponse,
    ReviewCreate, ReviewResponse, ProductSearchResponse
)
from features.marketplace.service import MarketplaceService
from features.auth.models import User
from features.users.models import FarmerProfile
from core.dependencies import get_current_active_user

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

@router.get("/products", response_model=ProductSearchResponse)
async def get_all_products(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    service = MarketplaceService(db)
    
    # Get all products without any filters
    products = service.get_all_products(skip=skip, limit=limit)
    
    print(f"DEBUG: Found {len(products)} products")
    
    # Convert to public response format
    public_products = []
    for product in products:
        # Get farmer profile
        farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
        
        # Parse images
        images = []
        if product.images:
            if isinstance(product.images, str):
                images = [img.strip() for img in product.images.split(',') if img.strip()]
            elif isinstance(product.images, list):
                images = product.images
        
        # Calculate discounted price
        discounted_price = product.price * (1 - (product.discount_percentage or 0) / 100)
        
        public_products.append(ProductPublicResponse(
            id=product.id,
            name=product.name,
            category=product.category,
            description=product.description or "",
            quantity=product.quantity,
            price=product.price,
            discount_percentage=product.discount_percentage or 0.0,
            discounted_price=discounted_price,
            location=product.location,
            images=images,
            availability=product.availability,
            total_ratings=product.total_ratings or 0,
            average_rating=product.average_rating or 0.0,
            created_at=product.created_at,
            updated_at=product.updated_at,
            farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
            farmer_name=farmer_profile.full_name if farmer_profile else "Farmer",
            farmer_id=product.farmer_id,
            is_approved=product.is_approved,
            is_listed=product.is_listed
        ))
    
    # Get total count for pagination
    total_count = service.get_total_product_count()
    
    return ProductSearchResponse(
        products=public_products,
        total_count=total_count,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
        has_next=(skip + limit) < total_count,
        has_previous=skip > 0
    )

# Categories endpoint
@router.get("/categories")
async def get_product_categories():
    """Get available product categories for filtering"""
    return {
        "categories": [
            {"id": "vegetables", "name": "Vegetables", "icon": "🥬"},
            {"id": "fruits", "name": "Fruits", "icon": "🍎"},
            {"id": "grains", "name": "Grains", "icon": "🌾"},
            {"id": "proteins", "name": "Proteins", "icon": "🥚"},
            {"id": "crop", "name": "Crops", "icon": "🌱"},
            {"id": "livestock", "name": "Livestock", "icon": "🐄"}
        ]
    }


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
async def get_product_detail(product_id: int, db: Session = Depends(get_db)):
    service = MarketplaceService(db)
    product = service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get farmer info from farmer profile
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
    if not farmer_profile:
        raise HTTPException(status_code=404, detail="Farmer profile not found")
    
    # Convert images
    images = []
    if product.images:
        if isinstance(product.images, str):
            images = [img.strip() for img in product.images.split(',') if img.strip()]
        elif isinstance(product.images, list):
            images = product.images
    
    # Calculate discounted price
    discounted_price = product.price * (1 - (product.discount_percentage or 0) / 100)
    
    return ProductDetailResponse(
        id=product.id,
        farmer_id=product.farmer_id,
        name=product.name,
        category=product.category,
        description=product.description or "",
        quantity=product.quantity,
        price=product.price,
        discount_percentage=product.discount_percentage or 0.0,
        location=product.location,
        images=images,
        is_approved=product.is_approved,
        is_listed=product.is_listed,
        availability=product.availability,
        total_ratings=product.total_ratings or 0,
        average_rating=product.average_rating or 0.0,
        created_at=product.created_at,
        updated_at=product.updated_at,
        farmer={
            "id": product.farmer_id,
            "full_name": farmer_profile.full_name,
            "profile_picture": farmer_profile.profile_picture,
            "farm_name": farmer_profile.farm_name,
            "farm_location": farmer_profile.farm_location,
            "farm_type": farmer_profile.farm_type.value if farmer_profile.farm_type else "Unknown"
        },
        discounted_price=discounted_price
    )

# Farmer product management
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
        
        # Convert images back to list for response
        images = []
        if product.images:
            if isinstance(product.images, str):
                images = [img.strip() for img in product.images.split(',') if img.strip()]
            elif isinstance(product.images, list):
                images = product.images
        
        return ProductResponse(
            id=product.id,
            farmer_id=product.farmer_id,
            name=product.name,
            category=product.category,
            description=product.description or "",
            quantity=product.quantity,
            price=product.price,
            discount_percentage=product.discount_percentage or 0.0,
            location=product.location,
            images=images,
            is_approved=product.is_approved,
            is_listed=product.is_listed,
            availability=product.availability,
            total_ratings=product.total_ratings or 0,
            average_rating=product.average_rating or 0.0,
            created_at=product.created_at,
            updated_at=product.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating product: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/farmers/products", response_model=List[ProductResponse])
async def get_my_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can view their products")
    
    service = MarketplaceService(db)
    products = service.get_farmer_products(current_user.id)
    
    response_products = []
    for product in products:
        images = []
        if product.images:
            if isinstance(product.images, str):
                images = [img.strip() for img in product.images.split(',') if img.strip()]
            elif isinstance(product.images, list):
                images = product.images
        
        response_products.append(ProductResponse(
            id=product.id,
            farmer_id=product.farmer_id,
            name=product.name,
            category=product.category,
            description=product.description or "",
            quantity=product.quantity,
            price=product.price,
            discount_percentage=product.discount_percentage or 0.0,
            location=product.location,
            images=images,
            is_approved=product.is_approved,
            is_listed=product.is_listed,
            availability=product.availability,
            total_ratings=product.total_ratings or 0,
            average_rating=product.average_rating or 0.0,
            created_at=product.created_at,
            updated_at=product.updated_at
        ))
    
    return response_products

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
    
    # Convert images back to list for response
    images = []
    if product.images:
        if isinstance(product.images, str):
            images = [img.strip() for img in product.images.split(',') if img.strip()]
        elif isinstance(product.images, list):
            images = product.images
    
    return ProductResponse(
        id=product.id,
        farmer_id=product.farmer_id,
        name=product.name,
        category=product.category,
        description=product.description or "",
        quantity=product.quantity,
        price=product.price,
        discount_percentage=product.discount_percentage or 0.0,
        location=product.location,
        images=images,
        is_approved=product.is_approved,
        is_listed=product.is_listed,
        availability=product.availability,
        total_ratings=product.total_ratings or 0,
        average_rating=product.average_rating or 0.0,
        created_at=product.created_at,
        updated_at=product.updated_at
    )

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

# Additional endpoints
@router.post("/farmers/products/{product_id}/discount")
async def add_discount(
    product_id: int,
    discount_percentage: float = Query(..., ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can add discounts")
    
    service = MarketplaceService(db)
    product = service.add_discount(product_id, current_user.id, discount_percentage)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Discount added successfully", "discount_percentage": product.discount_percentage}

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
    return {"message": "Discount removed successfully"}

# Order management
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

@router.get("/orders", response_model=List[OrderDetailResponse])
async def get_my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = MarketplaceService(db)
    orders = service.get_user_orders(current_user.id)
    
    enhanced_orders = []
    for order in orders:
        product = service.get_product(order.product_id)
        farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first() if product else None
        
        enhanced_orders.append(OrderDetailResponse(
            id=order.id,
            product_id=order.product_id,
            consumer_id=order.consumer_id,
            quantity_ordered=order.quantity_ordered,
            delivery_address=order.delivery_address,
            total_price=order.total_price,
            status=order.status,
            order_number=order.order_number,
            created_at=order.created_at,
            updated_at=order.updated_at,
            product_name=product.name if product else "Unknown Product",
            farm_name=farmer_profile.farm_name if farmer_profile else "Unknown Farm",
            farmer_name=farmer_profile.full_name if farmer_profile else "Farmer"
        ))
    
    return enhanced_orders

# Review management
@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = MarketplaceService(db)
    try:
        review = service.create_review(current_user.id, review_data)
        if not review:
            raise HTTPException(status_code=400, detail="Could not create review")
        return review
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/products/{product_id}/reviews", response_model=List[ReviewResponse])
async def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    service = MarketplaceService(db)
    reviews = service.get_product_reviews(product_id)
    
    response_reviews = []
    for review in reviews:
        response_reviews.append(ReviewResponse(
            id=review.id,
            product_id=review.product_id,
            consumer_id=review.consumer_id,
            rating=review.rating,
            comment=review.comment,
            created_at=review.created_at,
            consumer_name=f"User {review.consumer_id}"
        ))
    
    return response_reviews

# Search endpoint
@router.get("/products/search/suggestions")
async def search_suggestions(
    q: str = Query(..., description="Search query"),
    db: Session = Depends(get_db)
):
    """Get search suggestions"""
    service = MarketplaceService(db)
    products = service.search_products(q, limit=5)
    
    suggestions = []
    for product in products:
        suggestions.append({
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price": product.price
        })
    
    return {"suggestions": suggestions}