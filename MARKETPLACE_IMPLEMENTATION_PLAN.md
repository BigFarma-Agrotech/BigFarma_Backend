# BigFarma Marketplace Implementation Plan

## Overview
This document outlines the missing features and implementation steps needed to complete the BigFarma marketplace functionality for both consumers and farmers.

## Current Status

### ✅ Implemented Features

#### Consumer Features
- [x] Browse products with pagination
- [x] Search products by name and description
- [x] Filter by category (vegetables, fruits, grains, proteins)
- [x] Filter by price range (min/max)
- [x] Filter by location
- [x] Filter by availability (in_stock, out_of_stock, all)
- [x] Sort products (price_asc, price_desc, rating, newest)
- [x] Spelling suggestions ("Did you mean?")
- [x] Related products when no results
- [x] Filter suggestions when no results
- [x] Out of stock indication in listings

#### Farmer Features
- [x] Create product listings
- [x] View own products
- [x] Edit products
- [x] Delete/unlist products
- [x] Add/remove discounts
- [x] Duplicate product detection (partially - in service but has errors)

### ❌ Missing Features

#### Critical Database Changes Needed

1. **Product Status Field**
   - Current: Only has `is_approved` and `is_listed` boolean fields
   - Needed: `status` enum field with values: PENDING, ACTIVE, OUT_OF_STOCK, UNLISTED
   - Impact: Cannot show pending products or implement admin approval workflow

2. **Quantity Field Type**
   - Current: `quantity` is a string (e.g., "50kg", "10 goats")
   - Needed: Separate fields:
     - `quantity_unit` (string): "kg", "pieces", "goats", etc.
     - `quantity_available` (integer): Numeric value for calculations
   - Impact: Cannot auto-update stock when orders are placed

3. **Draft/Auto-save Fields**
   - Needed: `is_draft` boolean field
   - Needed: `draft_data` JSON field for incomplete forms
   - Impact: Cannot save incomplete product listings

## Implementation Plan

### Phase 1: Database Schema Updates (Priority: HIGH)

#### 1.1 Create Migration for Product Status
```python
# New migration file: add_product_status.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create status enum
    status_enum = postgresql.ENUM('pending', 'active', 'out_of_stock', 'unlisted', name='product_status')
    status_enum.create(op.get_bind())
    
    # Add status column
    op.add_column('products', sa.Column('status', sa.Enum('pending', 'active', 'out_of_stock', 'unlisted', name='product_status'), nullable=False, server_default='pending'))
    
    # Update existing products
    op.execute("UPDATE products SET status = 'active' WHERE is_approved = true AND is_listed = true")
    op.execute("UPDATE products SET status = 'unlisted' WHERE is_listed = false")
```

#### 1.2 Create Migration for Quantity Fields
```python
# New migration file: add_quantity_fields.py
def upgrade():
    op.add_column('products', sa.Column('quantity_available', sa.Integer, nullable=True))
    op.add_column('products', sa.Column('quantity_unit', sa.String(50), nullable=True))
    
    # Parse existing quantity strings
    # "50kg" -> quantity_available=50, quantity_unit="kg"
```

#### 1.3 Create Migration for Draft Support
```python
# New migration file: add_draft_support.py
def upgrade():
    op.add_column('products', sa.Column('is_draft', sa.Boolean, default=False))
    op.add_column('products', sa.Column('draft_data', sa.JSON, nullable=True))
```

### Phase 2: Model Updates (Priority: HIGH)

#### 2.1 Update Product Model
```python
class Product(Base):
    # ... existing fields ...
    
    # New fields
    status = Column(Enum(ProductStatus), default=ProductStatus.PENDING)
    quantity_available = Column(Integer, nullable=False)
    quantity_unit = Column(String(50), nullable=False)
    is_draft = Column(Boolean, default=False)
    draft_data = Column(JSON, nullable=True)
```

#### 2.2 Update Enums
```python
class ProductStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    OUT_OF_STOCK = "out_of_stock"
    UNLISTED = "unlisted"
```

### Phase 3: Service Layer Updates (Priority: HIGH)

#### 3.1 Fix Product Creation Validation
```python
def create_product(self, farmer_id: int, product_data: ProductCreate) -> Product:
    # Validation that actually works
    errors = []
    
    if not product_data.description or len(product_data.description) < 20:
        errors.append("Description must be at least 20 characters")
    
    if not product_data.images or len(product_data.images) == 0:
        errors.append("At least one image is required")
    
    if product_data.price <= 0:
        errors.append("Price must be greater than 0")
    
    if errors:
        raise ValueError("; ".join(errors))
```

#### 3.2 Add Stock Management
```python
def update_product_stock(self, product_id: int, quantity_ordered: int):
    product = self.get_product(product_id)
    if product:
        product.quantity_available -= quantity_ordered
        if product.quantity_available <= 0:
            product.status = ProductStatus.OUT_OF_STOCK
            product.quantity_available = 0
        self.db.commit()
```

#### 3.3 Add Draft Management
```python
def save_product_draft(self, farmer_id: int, draft_data: dict) -> Product:
    product = Product(
        farmer_id=farmer_id,
        name=draft_data.get('name', 'Untitled'),
        is_draft=True,
        draft_data=draft_data,
        # Set defaults for required fields
        category=ProductCategory.CROP,
        quantity="0",
        price=0,
        images=""
    )
    self.db.add(product)
    self.db.commit()
    return product
```

### Phase 4: API Endpoints Updates (Priority: MEDIUM)

#### 4.1 Add Admin Endpoints
```python
@router.post("/admin/products/{product_id}/approve")
async def approve_product(product_id: int, current_user: User = Depends(get_current_admin)):
    # Change status from PENDING to ACTIVE
    
@router.get("/admin/products/pending")
async def get_pending_products(current_user: User = Depends(get_current_admin)):
    # Return all products with PENDING status
```

#### 4.2 Add Draft Endpoints
```python
@router.post("/farmers/products/draft")
async def save_product_draft(draft_data: dict, current_user: User = Depends(get_current_active_user)):
    # Save incomplete product form
    
@router.get("/farmers/products/drafts")
async def get_my_drafts(current_user: User = Depends(get_current_active_user)):
    # Return all draft products for farmer
```

#### 4.3 Update Farmer Products Endpoint
```python
@router.get("/farmers/products")
async def get_my_products(
    include_drafts: bool = False,
    status: Optional[str] = None,
    # ... existing params
):
    # Return products with status filtering
```

### Phase 5: Frontend Integration Requirements (Priority: LOW)

#### 5.1 Consumer Interface
- Show product status badges (Active, Out of Stock)
- Handle "Clear Filters" action with API call
- Display product completeness warnings

#### 5.2 Farmer Interface
- Show product status (Pending, Active, Out of Stock, Unlisted)
- Auto-save form data every 30 seconds
- Resume from draft functionality
- Show validation errors in real-time

## Testing Requirements

### Unit Tests
- [ ] Test product validation rules
- [ ] Test duplicate detection
- [ ] Test stock management
- [ ] Test draft save/resume

### Integration Tests
- [ ] Test admin approval workflow
- [ ] Test order placement updates stock
- [ ] Test farmer product lifecycle

## Risk Mitigation

1. **Data Migration Risk**: Backup database before migrations
2. **Breaking Changes**: Version API endpoints (/api/v2/)
3. **Performance**: Add indexes on new status fields
4. **Validation Errors**: Add comprehensive error messages

## Success Metrics

- Zero incomplete product listings in production
- 90% of products have images and descriptions
- Stock levels accurately reflect available inventory
- Farmers can recover 100% of draft products
- Admin approval time < 24 hours

## Notes

- Current validation in routes is not working because exceptions from service layer are not properly caught
- AvailabilityStatus enum conflicts with new ProductStatus approach
- Consider using numeric IDs for categories instead of string enums for better performance
