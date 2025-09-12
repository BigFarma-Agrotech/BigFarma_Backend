# BigFarma Orders API 

A comprehensive order management system for the BigFarma agricultural marketplace platform.

## 📋 Overview

The Orders feature provides complete order lifecycle management, tracking, issue reporting, and delivery confirmation capabilities. It's designed to match the Figma designs and provides all the functionality shown in the UI mockups.

## 🏗️ Architecture

```
features/orders/
├── models.py      # Order timeline and issue models
├── schemas.py     # Pydantic models for API
├── service.py     # Business logic
├── routes.py      # FastAPI endpoints
└── __init__.py
```

The Orders feature is **modular and independent** from the Marketplace feature but **utilizes existing models** like `Order`, `Product`, and `User` from the marketplace.

## 🔧 Features Implemented

### ✅ Core Functionality (Matching Figma Design)
- **Order Listing**: View all orders with filtering and search
- **Order Details**: Comprehensive order information with timeline
- **Order Timeline**: Visual progress tracking (Placed → Shipping → Delivered)
- **Delivery Confirmation**: Consumer can confirm receipt
- **Issue Reporting**: Report delivery problems with description
- **Order Statistics**: Analytics dashboard for users
- **Status Updates**: Real-time order status management

### ✅ Order Statuses
- `pending` - Order placed but not confirmed
- `confirmed` - Farmer confirmed the order  
- `shipping` - Order is in transit
- `awaiting_confirmation` - Delivered, awaiting consumer confirmation
- `delivered` - Successfully completed
- `cancelled` - Order cancelled
- `delivery_issue` - Problem reported

### ✅ Timeline Tracking
- **Placed**: Order successfully placed
- **Shipping In Progress**: Order is being delivered
- **Delivered To Customer**: Handed off to customer
- **Awaiting Confirmation**: Waiting for customer confirmation
- **Delivered**: Order fully completed

## 🚀 API Endpoints

### Consumer Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/orders/` | Get all user orders with filtering |
| `GET` | `/api/v1/orders/{order_id}` | Get detailed order information |
| `POST` | `/api/v1/orders/{order_id}/report-issue` | Report delivery issue |
| `POST` | `/api/v1/orders/{order_id}/confirm-delivery` | Confirm order delivery |
| `GET` | `/api/v1/orders/{order_id}/timeline` | Get order timeline |
| `GET` | `/api/v1/orders/{order_id}/issues` | Get order issues |
| `GET` | `/api/v1/orders/statistics/summary` | Get order statistics |

### Farmer/Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/api/v1/orders/{order_id}/status` | Update order status |

## 📊 Sample Data

The system includes comprehensive sample data generation:

### 🧑‍🌾 Sample Farmers
- **GreenRoots Farm** (john.farmer@bigfarma.com) - Ikeja, Lagos
- **Adaku Farm** (mary.adaku@bigfarma.com) - Abuja, FCT  
- **Dan Farm** (ibrahim.dan@bigfarma.com) - Kano State
- **SunnyCoop** (sunny.coop@bigfarma.com) - Ogun State

### 🛒 Sample Consumers
- **Jane Smith** (jane.consumer@bigfarma.com) - Victoria Island, Lagos
- **Ahmed Musa** (ahmed.buyer@bigfarma.com) - Garki, Abuja
- **Grace Okoro** (grace.okoro@bigfarma.com) - Port Harcourt, Rivers

### 📦 Sample Products & Orders
- Fresh Tomatoes (Basket) - ₦5,000
- Fresh Peppers (Basket) - ₦8,000 (15% discount)
- Watermelon (5 Pcs) - ₦12,000
- Potatoes (5kg) - ₦3,500  
- Eggs (30 Crates) - ₦45,000 (5% discount)

**Orders with different statuses:**
- ✅ Delivered orders with reviews
- ⏰ Awaiting confirmation orders
- 🚚 Shipping in progress
- ⚠️ Orders with delivery issues
- ⏳ Pending orders

## 🧪 Testing

### Setup Test Environment

1. **Create sample data:**
```bash
python create_sample_data.py
```

2. **Run the server:**
```bash
uvicorn main:app --reload
```

3. **Test the API:**
```bash
# Quick test
python test_orders_api.py quick

# Comprehensive test
python test_orders_api.py
```

### Manual Testing with cURL

```bash
# Login as consumer
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "jane.consumer@bigfarma.com", "password": "consumer123"}'

# Get orders (use token from login)
curl -X GET http://localhost:8000/api/v1/orders/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get order details
curl -X GET http://localhost:8000/api/v1/orders/1 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Report delivery issue
curl -X POST http://localhost:8000/api/v1/orders/1/report-issue \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"issue_description": "Package was damaged during delivery"}'

# Confirm delivery
curl -X POST http://localhost:8000/api/v1/orders/2/confirm-delivery \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🎨 Frontend Integration

The API responses are designed to match the Figma design requirements:

### Order List Response
```json
{
  "id": 1,
  "order_number": "BF20241201ABC12345",
  "product_name": "Fresh Tomatoes (Basket)",
  "farm_name": "GreenRoots Farm", 
  "farmer_name": "John Doe",
  "status": "delivered",
  "total_price": 5000.0,
  "created_at": "2024-12-01T10:00:00Z"
}
```

### Order Details Response
```json
{
  "id": 1,
  "order_number": "BF20241201ABC12345",
  "product_name": "Fresh Tomatoes (Basket)",
  "farm_name": "GreenRoots Farm",
  "timeline": [
    {
      "title": "Order Placed",
      "description": "Your order has been placed successfully", 
      "is_completed": true,
      "completed_at": "2024-12-01T10:00:00Z"
    },
    {
      "title": "Shipping In Progress",
      "description": "Your order is on its way",
      "is_completed": true,
      "completed_at": "2024-12-01T16:00:00Z"
    }
  ],
  "issues": [
    {
      "issue_description": "Package left at gate, items missing",
      "status": "reported",
      "created_at": "2024-12-02T09:00:00Z"
    }
  ]
}
```

## 🔄 Integration with Marketplace

The Orders feature seamlessly integrates with the existing Marketplace:

- **Reuses Models**: Uses `Order`, `Product`, `User` from marketplace
- **Extends Functionality**: Adds timeline and issue tracking
- **Independent Routes**: Separate API endpoints under `/orders`
- **Shared Database**: Uses same database tables with extensions

## 🚦 Order Flow

1. **Order Creation** (via Marketplace API)
   - Consumer places order through marketplace
   - Order created with `PENDING` status
   - Initial timeline entry added

2. **Farmer Confirmation** 
   - Farmer updates status to `CONFIRMED`
   - Timeline updated automatically

3. **Shipping**
   - Status updated to `SHIPPING`
   - "Shipping In Progress" timeline entry

4. **Delivery Attempt**
   - Status updated to `AWAITING_CONFIRMATION`
   - Consumer notified to confirm receipt

5. **Completion Paths**
   - ✅ **Success**: Consumer confirms → `DELIVERED`
   - ⚠️ **Issue**: Consumer reports problem → `DELIVERY_ISSUE`

## 📱 UI Components Supported

The API supports all UI components shown in the Figma design:

- **Order Cards**: List view with status badges
- **Order Details Modal**: Full order information  
- **Timeline Component**: Visual progress tracker
- **Issue Reporting Modal**: Problem description form
- **Confirmation Buttons**: Delivery confirmation actions
- **Status Badges**: Color-coded order status indicators
- **Search & Filter**: Order filtering capabilities

## 🔒 Security & Authorization

- **JWT Authentication**: All endpoints require valid JWT token
- **User Authorization**: Users can only access their own orders
- **Role-based Access**: Farmers can update order status
- **Input Validation**: Pydantic schemas validate all inputs
- **SQL Injection Protection**: SQLAlchemy ORM prevents injection

## 🎯 Next Steps

To fully implement the Figma design:

1. **Frontend Integration**: Connect React/Vue.js components to API
2. **Real-time Updates**: Add WebSocket support for live order tracking  
3. **Notification System**: Email/SMS alerts for status changes
4. **Admin Panel**: Order management dashboard for administrators
5. **Analytics Dashboard**: Enhanced reporting and insights
6. **Mobile App**: Responsive design for mobile users

## 🤝 Contributing

The Orders feature is designed to be:
- **Modular**: Independent from other features
- **Extensible**: Easy to add new functionality
- **Testable**: Comprehensive test coverage
- **Documented**: Clear API documentation

Ready for production use and frontend integration! 🚀
