# BigFarma Backend Refactoring Notes

## Date: December 2024

### Change #1: Removed Duplicate Order Listing Endpoint

**What was changed:**
- Removed `GET /marketplace/orders` endpoint from `features/marketplace/routes.py`
- Removed unused `OrderDetailResponse` import from marketplace routes

**Why:**
- The marketplace feature had a basic order listing endpoint that duplicated functionality
- The orders feature provides a more comprehensive order management system with:
  - Advanced filtering and search
  - Order timeline tracking  
  - Issue reporting
  - Better response structure

**Impact:**
- Frontend should now use `GET /api/v1/orders/` instead of `GET /api/v1/marketplace/orders`
- The orders endpoint provides all the same data plus additional features
- No breaking changes to order creation - `POST /marketplace/orders` remains unchanged

**Migration Guide:**
1. Update any frontend code that calls `/api/v1/marketplace/orders` to use `/api/v1/orders/`
2. The response structure is similar but enhanced with additional fields
3. Authentication remains the same (JWT token required)

### Notes:
- The `get_user_orders` method in `MarketplaceService` was kept for potential internal use
- Order creation still happens through the marketplace (`POST /marketplace/orders`)
- All post-purchase order management should use the orders feature endpoints

### Testing:
After these changes, ensure to:
1. Test that order creation still works via marketplace
2. Verify order listing works via the orders endpoint
3. Check that all order management features (timeline, issues, confirmation) still function

**Note on Testing**: When testing the removed endpoint, you'll get a 405 (Method Not Allowed) status instead of 404. This is correct because:
- The route `/marketplace/orders` still exists for POST (order creation)
- Only the GET method was removed
- 405 indicates the route exists but doesn't support the requested method
