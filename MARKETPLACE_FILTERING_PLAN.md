# BigFarma Marketplace Filtering Implementation Plan

## Current State Analysis

### What's Missing:
1. **Category Filtering** - The API only has CROP/LIVESTOCK but UI needs Vegetables/Fruits/Grains/Proteins
2. **Search Functionality** - No text search for product names
3. **Advanced Filters** - No support for price range, location, ratings, etc.

### Current Endpoint:
```
GET /api/v1/marketplace/products?skip=0&limit=100
```
Only supports pagination, no filtering!

## Implementation Approach

### Option 1: Add Subcategory Field (Recommended)
Keep the main category (CROP/LIVESTOCK) and add a subcategory field:

```python
class ProductSubcategory(str, enum.Enum):
    # Crop subcategories
    VEGETABLES = "vegetables"
    FRUITS = "fruits"
    GRAINS = "grains"
    # Livestock subcategories
    PROTEINS = "proteins"  # Could include eggs, meat, dairy
```

### Option 2: Expand Main Categories
Change ProductCategory to match UI exactly:
```python
class ProductCategory(str, enum.Enum):
    VEGETABLES = "vegetables"
    FRUITS = "fruits"
    GRAINS = "grains"
    PROTEINS = "proteins"
```

## Required Changes:

### 1. Update Routes (marketplace/routes.py)
```python
@router.get("/products", response_model=List[ProductPublicResponse])
async def get_all_products(
    skip: int = 0, 
    limit: int = 100,
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search product names"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    location: Optional[str] = Query(None, description="Filter by location"),
    availability: Optional[str] = Query(None, description="Filter by availability status"),
    db: Session = Depends(get_db)
):
```

### 2. Update Service (marketplace/service.py)
```python
def get_all_products(
    self, 
    skip: int = 0, 
    limit: int = 100,
    category: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    location: Optional[str] = None,
    availability: Optional[str] = None
) -> List[Product]:
    query = self.db.query(Product).filter(
        Product.is_approved == True, 
        Product.is_listed == True
    )
    
    # Add filters
    if category:
        query = query.filter(Product.category == category)
    
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    
    if min_price:
        query = query.filter(Product.price >= min_price)
        
    if max_price:
        query = query.filter(Product.price <= max_price)
        
    if location:
        query = query.filter(Product.location.ilike(f"%{location}%"))
        
    if availability:
        query = query.filter(Product.availability == availability)
    
    return query.offset(skip).limit(limit).all()
```

### 3. Add Categories Endpoint
```python
@router.get("/categories")
async def get_categories():
    """Get available product categories for filtering"""
    return {
        "categories": [
            {"id": "vegetables", "name": "Vegetables", "icon": "🥬", "parent": "crop"},
            {"id": "fruits", "name": "Fruits", "icon": "🍎", "parent": "crop"},
            {"id": "grains", "name": "Grains", "icon": "🌾", "parent": "crop"},
            {"id": "proteins", "name": "Proteins", "icon": "🥚", "parent": "livestock"}
        ]
    }
```

## Quick Fix (Without Database Migration)

If you need to implement this quickly without changing the database:

1. Map UI categories to existing database categories in the API
2. Use product names/descriptions to infer subcategories

```python
def map_ui_category_to_db(ui_category: str) -> str:
    """Map UI categories to database categories"""
    mapping = {
        "vegetables": "crop",
        "fruits": "crop",
        "grains": "crop",
        "proteins": "livestock"
    }
    return mapping.get(ui_category.lower())
```

## Testing the Implementation

```bash
# Search for tomatoes
GET /api/v1/marketplace/products?search=tomato

# Filter by vegetables (mapped to crop)
GET /api/v1/marketplace/products?category=vegetables

# Combined filters
GET /api/v1/marketplace/products?category=fruits&min_price=1000&max_price=5000

# Get available categories
GET /api/v1/marketplace/categories
```

## Priority Order:
1. ✅ Add search parameter (easiest, highest impact)
2. ✅ Add category filtering with mapping
3. ✅ Add price range filters
4. ⭐ Add categories endpoint
5. 📍 Add location filter
6. ⚡ Add availability filter

This would make the marketplace fully functional as shown in the UI!
