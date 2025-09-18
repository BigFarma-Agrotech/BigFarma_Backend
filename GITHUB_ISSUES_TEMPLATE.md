# GitHub Issues for BigFarma Marketplace Implementation

## Issue #1: Add Product Status Management System

**Title**: Implement Product Status Workflow (Pending → Active → Out of Stock)

**Labels**: `enhancement`, `backend`, `database`, `priority:high`

**Description**:
Currently, products only have boolean flags (`is_approved`, `is_listed`). We need a proper status enum to track product lifecycle.

**Acceptance Criteria**:
- [ ] Add `status` enum column with values: PENDING, ACTIVE, OUT_OF_STOCK, UNLISTED
- [ ] Migrate existing products to appropriate status
- [ ] New products default to PENDING status
- [ ] Products show correct status in API responses

**Tasks**:
- [ ] Create alembic migration for status enum
- [ ] Update Product model
- [ ] Update service methods to use new status
- [ ] Update API responses to include status

**Blocked by**: None
**Blocks**: Issue #6 (Admin Approval Workflow)

---

## Issue #2: Fix Product Creation Validation

**Title**: Product validation not working in create endpoint

**Labels**: `bug`, `backend`, `priority:high`

**Description**:
Validation in the `/farmers/products` POST endpoint is not working. Products with incomplete data (short descriptions, no images, zero price) are being accepted.

**Current Behavior**:
- Products with <20 char descriptions are accepted
- Products without images are accepted
- Products with price=0 are accepted

**Expected Behavior**:
- Return 400 error with specific validation message
- Block creation of incomplete products

**Steps to Reproduce**:
1. POST to `/api/v1/marketplace/farmers/products` with incomplete data
2. Observe 201 response instead of 400 error

**Tasks**:
- [ ] Fix exception handling in route
- [ ] Ensure service layer validation errors bubble up
- [ ] Add integration tests for validation

---

## Issue #3: Implement Numeric Quantity Tracking

**Title**: Convert string quantity to numeric fields for stock management

**Labels**: `enhancement`, `backend`, `database`, `priority:high`

**Description**:
Current `quantity` field is a string (e.g., "50kg", "10 goats"). Need numeric tracking for auto-stock updates.

**Acceptance Criteria**:
- [ ] Add `quantity_available` (integer) field
- [ ] Add `quantity_unit` (string) field
- [ ] Migrate existing quantity strings to new fields
- [ ] Auto-decrement stock when orders are placed

**Migration Strategy**:
```
"50kg" → quantity_available=50, quantity_unit="kg"
"10 goats" → quantity_available=10, quantity_unit="goats"
```

**Tasks**:
- [ ] Create migration to add new fields
- [ ] Write parser for existing quantity strings
- [ ] Update create_order to decrement stock
- [ ] Add stock validation before order creation

**Blocked by**: None
**Blocks**: Issue #7 (Auto Stock Management)

---

## Issue #4: Add Duplicate Product Detection

**Title**: Detect and prevent duplicate product listings

**Labels**: `enhancement`, `backend`, `priority:medium`

**Description**:
Farmers should not be able to create duplicate products. System should detect existing products and suggest editing.

**Acceptance Criteria**:
- [ ] Check for duplicate by product name (case-insensitive)
- [ ] Return specific error: "Product 'X' already exists. Please edit the existing listing."
- [ ] Only check active/pending products (not unlisted)

**Current Status**: 
Code exists in service but has bugs due to model issues

**Tasks**:
- [ ] Fix duplicate check in create_product service
- [ ] Add proper error response in API
- [ ] Add unit tests for duplicate detection

---

## Issue #5: Implement Draft/Auto-save Feature

**Title**: Add draft saving for incomplete product forms

**Labels**: `enhancement`, `backend`, `database`, `priority:medium`

**Description**:
Farmers should be able to save incomplete product forms and resume later.

**Acceptance Criteria**:
- [ ] Add `is_draft` boolean field
- [ ] Add `draft_data` JSON field
- [ ] Create `/farmers/products/draft` endpoint
- [ ] Create `/farmers/products/drafts` GET endpoint
- [ ] Allow converting draft to complete product

**API Endpoints**:
```
POST /api/v1/marketplace/farmers/products/draft
GET /api/v1/marketplace/farmers/products/drafts
PUT /api/v1/marketplace/farmers/products/draft/{draft_id}/complete
```

**Tasks**:
- [ ] Add draft fields to database
- [ ] Create draft service methods
- [ ] Implement draft API endpoints
- [ ] Add auto-save logic documentation

**Blocked by**: None

---

## Issue #6: Create Admin Approval Workflow

**Title**: Implement admin approval for new product listings

**Labels**: `enhancement`, `backend`, `feature`, `priority:medium`

**Description**:
New products should require admin approval before becoming visible to consumers.

**Acceptance Criteria**:
- [ ] Products start with PENDING status
- [ ] Admin endpoint to list pending products
- [ ] Admin endpoint to approve/reject products
- [ ] Email notification on approval (future)

**API Endpoints**:
```
GET /api/v1/marketplace/admin/products/pending
POST /api/v1/marketplace/admin/products/{id}/approve
POST /api/v1/marketplace/admin/products/{id}/reject
```

**Tasks**:
- [ ] Create admin-only endpoints
- [ ] Add admin authorization checks
- [ ] Update product visibility logic
- [ ] Add approval timestamp field

**Blocked by**: Issue #1 (Product Status)

---

## Issue #7: Fix Auto Stock Management

**Title**: Automatically update product stock when orders are placed

**Labels**: `enhancement`, `backend`, `priority:high`

**Description**:
Currently, products are marked as OUT_OF_STOCK after first order. Should properly decrement available quantity.

**Current Behavior**:
- First order sets product to OUT_OF_STOCK regardless of quantity

**Expected Behavior**:
- Decrement quantity_available by order amount
- Set OUT_OF_STOCK only when quantity_available reaches 0

**Tasks**:
- [ ] Fix create_order stock update logic
- [ ] Add quantity parsing for order amounts
- [ ] Validate sufficient stock before order
- [ ] Add transaction to prevent overselling

**Blocked by**: Issue #3 (Numeric Quantity)

---

## Issue #8: Add Product Completeness Indicators

**Title**: Show product completeness warnings in API responses

**Labels**: `enhancement`, `backend`, `priority:low`

**Description**:
API should indicate if products are missing important information so frontend can show warnings.

**Acceptance Criteria**:
- [ ] Add `is_complete` field to product responses
- [ ] Add `missing_fields` array listing what's incomplete
- [ ] Check: description length, images, price, quantity, location

**Example Response**:
```json
{
  "id": 1,
  "name": "Tomatoes",
  "is_complete": false,
  "missing_fields": ["description too short", "no images"]
}
```

**Tasks**:
- [ ] Add completeness check method
- [ ] Include in product responses
- [ ] Document completeness criteria

---

## Issue #9: Add Clear Filters API Support

**Title**: Ensure clear filters action triggers fresh API call

**Labels**: `enhancement`, `frontend`, `backend`, `priority:low`

**Description**:
When users clear filters in the UI, it should trigger a fresh API call to get unfiltered results.

**Backend Requirements**:
- [ ] Document that frontend should call API without query params
- [ ] Ensure default behavior returns all products

**Frontend Requirements**:
- [ ] Clear all filter state
- [ ] Make new API call without parameters

---

## Issue #10: Add Farmer Product Status Display

**Title**: Show product status (Active, Pending, Out of Stock) in farmer dashboard

**Labels**: `enhancement`, `backend`, `frontend`, `priority:medium`

**Description**:
Farmers need to see the status of their products in their dashboard.

**Acceptance Criteria**:
- [ ] Include status in `/farmers/products` response
- [ ] Allow filtering by status
- [ ] Show count of products by status

**API Updates**:
```
GET /api/v1/marketplace/farmers/products?status=pending
GET /api/v1/marketplace/farmers/products/stats
```

**Tasks**:
- [ ] Add status filter to get_farmer_products
- [ ] Create stats endpoint
- [ ] Update response schemas

**Blocked by**: Issue #1 (Product Status)

---

## Meta Issue: Marketplace Implementation Tracking

**Title**: [META] Complete Marketplace Feature Implementation

**Labels**: `epic`, `tracking`

**Description**:
Parent issue to track all marketplace implementation tasks.

**Consumer Features Status**:
- [x] Browse products
- [x] Search products
- [x] Filter by category, price, location
- [x] Sort products
- [x] Spelling suggestions
- [x] Out of stock indication
- [ ] Clear filters action (Issue #9)

**Farmer Features Status**:
- [x] Create products (validation broken - Issue #2)
- [x] View/Edit/Delete products
- [ ] Product status display (Issue #10)
- [ ] Duplicate detection (Issue #4)
- [ ] Draft/Auto-save (Issue #5)
- [ ] Stock management (Issue #7)

**Admin Features Status**:
- [ ] Approval workflow (Issue #6)
- [ ] Pending products list
- [ ] Approve/Reject products

**Related Issues**:
- #1 Product Status Management
- #2 Fix Validation
- #3 Numeric Quantity
- #4 Duplicate Detection
- #5 Draft Feature
- #6 Admin Approval
- #7 Stock Management
- #8 Completeness Indicators
- #9 Clear Filters
- #10 Status Display

---

## Issue Templates

### Bug Report Template
```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
What should happen

**Actual behavior**
What actually happens

**Screenshots**
If applicable

**Environment**
- OS: [e.g. Windows 10]
- Python version: [e.g. 3.9]
- Browser: [e.g. Chrome]
```

### Feature Request Template
```markdown
**Is your feature request related to a problem?**
Description of the problem

**Describe the solution you'd like**
What you want to happen

**Describe alternatives you've considered**
Other solutions

**Additional context**
Any other context or screenshots
```
