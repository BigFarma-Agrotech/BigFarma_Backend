from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from difflib import get_close_matches

from database import get_db
from features.marketplace.schemas import (
    ProductCreate, ProductResponse, ProductUpdate, ProductDetailResponse,
    ProductPublicResponse, OrderCreate, OrderResponse, OrderDetailResponse,
    ReviewCreate, ReviewResponse, ProductSearchResponse, ProductFilterRequest
)
from features.marketplace.service import MarketplaceService
from features.auth.models import User
from features.users.models import FarmerProfile
from core.dependencies import get_current_active_user

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

# Categories endpoint
@router.get("/categories")
async def get_product_categories():
    """Get available product categories for filtering"""
    return {
        "categories": [
            {"id": "vegetables", "name": "Vegetables", "icon": "🥬", "parent": "crop"},
            {"id": "fruits", "name": "Fruits", "icon": "🍎", "parent": "crop"},
            {"id": "grains", "name": "Grains", "icon": "🌾", "parent": "crop"},
            {"id": "proteins", "name": "Proteins", "icon": "🥚", "parent": "livestock"}
        ]
    }

# Public endpoints
@router.get("/products", response_model=Dict[str, Any])
async def get_all_products(
    skip: int = 0, 
    limit: int = 100,
    category: Optional[str] = Query(None, description="Filter by category (vegetables, fruits, grains, proteins)"),
    search: Optional[str] = Query(None, description="Search product names"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    location: Optional[str] = Query(None, description="Filter by location"),
    availability: Optional[str] = Query(None, description="Filter by availability (in_stock, out_of_stock, all)"),
    sort_by: Optional[str] = Query(None, description="Sort by: price_asc, price_desc, rating, newest"),
    db: Session = Depends(get_db)
):
    service = MarketplaceService(db)
    
    # Map UI categories to database categories
    db_category = None
    if category:
        category_mapping = {
            "vegetables": "crop",
            "fruits": "crop",
            "grains": "crop",
            "proteins": "livestock"
        }
        db_category = category_mapping.get(category.lower())
    
    # Get products with filters
    products = service.get_all_products(
        skip=skip, 
        limit=limit,
        category=db_category,
        search=search,
        min_price=min_price,
        max_price=max_price,
        location=location,
        availability=availability,
        sort_by=sort_by
    )
    
    # Check for spelling suggestions if search is provided
    search_suggestions = []
    if search and len(products) == 0:
        # Common product names for spell checking
        common_products = [
            "tomato", "tomatoes", "pepper", "peppers", "onion", "onions",
            "rice", "beans", "corn", "maize", "yam", "potato", "potatoes",
            "carrot", "carrots", "cabbage", "lettuce", "spinach", "cucumber",
            "watermelon", "pineapple", "orange", "oranges", "banana", "apple",
            "chicken", "eggs", "beef", "fish", "milk"
        ]
        # Get close matches
        close_matches = get_close_matches(search.lower(), common_products, n=3, cutoff=0.6)
        search_suggestions = close_matches[:2]  # Max 2 suggestions
    
    # Convert to public response format
    public_products = []
    for product in products:
        # Get farmer profile
        farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
        
        # Parse images
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
    
    # Get total count for pagination
    total_count = service.get_products_count(
        category=db_category,
        search=search,
        min_price=min_price,
        max_price=max_price,
        location=location,
        availability=availability
    )
    
    # Prepare filter suggestions if no results
    filter_suggestions = []
    if len(products) == 0 and any([category, search, min_price, max_price, location]):
        # Suggest adjusting filters
        if min_price and max_price:
            filter_suggestions.append("Try expanding your price range")
        if location:
            filter_suggestions.append("Try searching in nearby locations")
        if category:
            filter_suggestions.append("Try browsing other categories")
    
    # Get related products if results are empty
    related_products = []
    if len(products) == 0:
        # Get some products from same category or any available products
        related = service.get_all_products(skip=0, limit=4, category=db_category)
        for rel_product in related:
            farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == rel_product.farmer_id).first()
            images = rel_product.images.split(',') if rel_product.images else []
            related_products.append({
                "id": rel_product.id,
                "name": rel_product.name,
                "price": rel_product.price,
                "images": images,
                "farm_name": farmer_profile.farm_name if farmer_profile else "Unknown Farm"
            })
    
    return {
        "products": public_products,
        "total_count": total_count,
        "page": skip // limit + 1,
        "page_size": limit,
        "search_suggestions": search_suggestions,
        "filter_suggestions": filter_suggestions,
        "related_products": related_products,
        "filters_applied": any([category, search, min_price, max_price, location, availability])
    }

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
    
    # Convert images from string to list
    images = product.images.split(',') if product.images else []
    
    product_dict = {
        "id": product.id,
        "farmer_id": product.farmer_id,
        "name": product.name,
        "category": product.category,
        "description": product.description,
        "quantity": product.quantity,
        "price": product.price,
        "discount_percentage": product.discount_percentage,
        "location": product.location,
        "images": images,
        "is_approved": product.is_approved,
        "is_listed": product.is_listed,
        "availability": product.availability,
        "total_ratings": product.total_ratings,
        "average_rating": product.average_rating,
        "created_at": product.created_at,
        "updated_at": product.updated_at
    }
    
    return ProductDetailResponse(
        **product_dict,
        farmer={
            "id": product.farmer.id,
            "full_name": farmer_profile.full_name,
            "profile_picture": farmer_profile.profile_picture,
            "farm_name": farmer_profile.farm_name,
            "farm_location": farmer_profile.farm_location,
            "farm_type": farmer_profile.farm_type.value if farmer_profile.farm_type else "Unknown"
        },
        discounted_price=product.price * (1 - product.discount_percentage / 100)
    )

# NEW ENDPOINTS FOR SEARCH AND FILTERING

@router.get("/products/search", response_model=ProductSearchResponse)
async def search_products(
    q: str = Query(..., description="Search query for products"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Search products by name, description, farm name, or crop type"""
    service = MarketplaceService(db)
    skip = (page - 1) * page_size
    
    products = service.search_products(q, skip, page_size)
    total_count = service.get_total_product_count()
    
    # Convert to public response with image handling
    public_products = []
    for product in products:
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
    
    return ProductSearchResponse(
        products=public_products,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.post("/products/filter", response_model=ProductSearchResponse)
async def filter_products(
    filters: ProductFilterRequest,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Filter products by various criteria"""
    service = MarketplaceService(db)
    skip = (page - 1) * page_size
    
    # Convert filters to dict
    filter_dict = filters.dict(exclude_unset=True)
    
    products = service.filter_products(filter_dict, skip, page_size)
    total_count = len(products)  # For simplicity, use the filtered count
    
    # Convert to public response
    public_products = []
    for product in products:
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
    
    return ProductSearchResponse(
        products=public_products,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/products/{product_id}/similar", response_model=List[ProductPublicResponse])
async def get_similar_products(
    product_id: int,
    limit: int = Query(6, ge=1, le=20, description="Number of similar products"),
    db: Session = Depends(get_db)
):
    """Get products similar to the specified product"""
    service = MarketplaceService(db)
    similar_products = service.get_similar_products(product_id, limit)
    
    # Convert to public response
    public_products = []
    for product in similar_products:
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

@router.get("/crops/{crop_type}/products", response_model=ProductSearchResponse)
async def get_products_by_crop_type(
    crop_type: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Get products filtered by specific crop type"""
    service = MarketplaceService(db)
    skip = (page - 1) * page_size
    
    products = service.get_products_by_crop_type(crop_type, skip, page_size)
    total_count = len(products)  # For simplicity
    
    # Convert to public response
    public_products = []
    for product in products:
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
    
    return ProductSearchResponse(
        products=public_products,
        total_count=total_count,
        page=page,
        page_size=page_size
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
    
    # Validate product completeness
    if not product_data.description or len(product_data.description) < 20:
        raise HTTPException(
            status_code=400, 
            detail="Product description must be at least 20 characters long"
        )
    
    if not product_data.images or len(product_data.images) == 0:
        raise HTTPException(
            status_code=400, 
            detail="At least one product image is required"
        )
    
    if product_data.price <= 0:
        raise HTTPException(
            status_code=400, 
            detail="Product price must be greater than 0"
        )
    
    service = MarketplaceService(db)
    try:
        product = service.create_product(current_user.id, product_data)
        
        # Convert images back to list for response
        product_dict = product.__dict__.copy()
        if isinstance(product_dict.get('images'), str):
            product_dict['images'] = product_dict['images'].split(',') if product_dict['images'] else []
        
        return ProductResponse(**product_dict)
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
    
    # Convert images back to list for response
    product_dict = product.__dict__.copy()
    if isinstance(product_dict.get('images'), str):
        product_dict['images'] = product_dict['images'].split(',') if product_dict['images'] else []
    
    return ProductResponse(**product_dict)

@router.get("/farmers/products", response_model=List[ProductResponse])
async def get_my_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.category != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can view their products")
    
    service = MarketplaceService(db)
    products = service.get_farmer_products(current_user.id)
    
    # Convert images from string to list for each product
    response_products = []
    for product in products:
        product_dict = product.__dict__.copy()
        if isinstance(product_dict.get('images'), str):
            product_dict['images'] = product_dict['images'].split(',') if product_dict['images'] else []
        response_products.append(ProductResponse(**product_dict))
    
    return response_products

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
    
    # Enhance order details
    enhanced_orders = []
    for order in orders:
        product = order.product
        farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == product.farmer_id).first()
        
        enhanced_orders.append(OrderDetailResponse(
            **order.__dict__,
            product_name=product.name,
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
    review = service.create_review(current_user.id, review_data)
    if not review:
        raise HTTPException(status_code=400, detail="Could not create review")
    return review

@router.get("/products/{product_id}/reviews", response_model=List[ReviewResponse])
async def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    service = MarketplaceService(db)
    return service.get_product_reviews(product_id)