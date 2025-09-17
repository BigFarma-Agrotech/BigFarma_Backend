"""
Comprehensive API Test Script for BigFarma Backend
Tests all endpoints: Auth, Users, Marketplace, Orders
"""

import requests
import json
from datetime import datetime
import time
from typing import Dict, Optional, List

# ANSI color codes for better output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class BigFarmaAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.tokens = {}
        self.created_resources = {
            "products": [],
            "orders": [],
            "reviews": []
        }
        self.test_results = []
    
    def print_header(self, text: str):
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}{text}{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}")
    
    def print_success(self, text: str):
        print(f"{GREEN}✓ {text}{RESET}")
        self.test_results.append(("PASS", text))
    
    def print_error(self, text: str):
        print(f"{RED}✗ {text}{RESET}")
        self.test_results.append(("FAIL", text))
    
    def print_info(self, text: str):
        print(f"{YELLOW}ℹ {text}{RESET}")
    
    def test_endpoint(self, method: str, endpoint: str, description: str, 
                     data: Optional[Dict] = None, headers: Optional[Dict] = None, 
                     expected_status: List[int] = [200], params: Optional[Dict] = None):
        """Generic endpoint tester"""
        try:
            url = f"{self.api_url}{endpoint}"
            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code in expected_status:
                self.print_success(f"{method} {endpoint}: {description} ({response.status_code})")
                return True, response
            else:
                self.print_error(f"{method} {endpoint}: {description} (Got {response.status_code}, Expected {expected_status})")
                if response.text:
                    print(f"  Response: {response.text[:200]}")
                return False, response
                
        except Exception as e:
            self.print_error(f"{method} {endpoint}: {description} - Error: {str(e)}")
            return False, None
    
    def test_health(self):
        """Test server health"""
        self.print_header("Testing Server Health")
        
        # Health endpoint is at /health, not under /api/v1
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                self.print_success("GET /health: Health check (200)")
                print(f"  Server status: {response.json().get('status', 'unknown')}")
            else:
                self.print_error(f"GET /health: Health check (Got {response.status_code}, Expected 200)")
        except Exception as e:
            self.print_error(f"GET /health: Health check - Error: {str(e)}")
    
    def test_auth_endpoints(self):
        """Test all authentication endpoints"""
        self.print_header("Testing Authentication Endpoints")
        
        # Test user registration
        test_users = [
            {
                "email": f"test_farmer_{int(time.time())}@test.com",
                "password": "Test123!@#",
                "category": "farmer"
            },
            {
                "email": f"test_consumer_{int(time.time())}@test.com",
                "password": "Test123!@#",
                "category": "consumer"
            }
        ]
        
        for user_data in test_users:
            # Register
            success, response = self.test_endpoint(
                "POST", "/auth/register", 
                f"Register {user_data['category']}", 
                data=user_data,
                expected_status=[200, 201, 400]  # 400 if already exists
            )
            
            # Login
            login_data = {
                "login": user_data["email"],
                "password": user_data["password"]
            }
            success, response = self.test_endpoint(
                "POST", "/auth/login",
                f"Login {user_data['category']}",
                data=login_data,
                expected_status=[200]
            )
            
            if success and response:
                token = response.json().get("access_token")
                self.tokens[user_data["category"]] = token
                self.print_info(f"  Stored {user_data['category']} token")
        
        # Test with existing users
        existing_users = [
            ("john.farmer@bigfarma.com", "farmer123", "farmer"),
            ("jane.consumer@bigfarma.com", "consumer123", "consumer")
        ]
        
        for email, password, category in existing_users:
            login_data = {"login": email, "password": password}
            success, response = self.test_endpoint(
                "POST", "/auth/login",
                f"Login existing {category}",
                data=login_data,
                expected_status=[200]
            )
            if success and response:
                self.tokens[f"existing_{category}"] = response.json().get("access_token")
    
    def test_user_endpoints(self):
        """Test user profile endpoints"""
        self.print_header("Testing User Endpoints")
        
        if not self.tokens:
            self.print_error("No authentication tokens available")
            return
        
        # Test get current user
        for user_type, token in self.tokens.items():
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get user profile (skip /users/me as it doesn't exist)
            self.test_endpoint(
                "GET", "/users/profile",
                f"Get user profile ({user_type})",
                headers=headers,
                expected_status=[200, 404]  # 404 if profile not created
            )
    
    def test_marketplace_endpoints(self):
        """Test all marketplace endpoints"""
        self.print_header("Testing Marketplace Endpoints")
        
        # Public endpoints (no auth required)
        self.print_info("Testing Public Endpoints...")
        
        # Get categories
        self.test_endpoint("GET", "/marketplace/categories", "Get product categories")
        
        # Get all products
        self.test_endpoint("GET", "/marketplace/products", "Get all products")
        
        # Test with filters
        filters = [
            {"search": "tomato"},
            {"category": "vegetables"},
            {"min_price": "1000", "max_price": "5000"},
            {"location": "lagos"},
            {"availability": "in_stock"},
            {"sort_by": "price_asc"},
            {"search": "tommato"},  # Misspelled for spell check test
        ]
        
        for filter_params in filters:
            filter_desc = ", ".join([f"{k}={v}" for k, v in filter_params.items()])
            self.test_endpoint(
                "GET", "/marketplace/products",
                f"Get products with filter: {filter_desc}",
                params=filter_params
            )
        
        # Get specific product (assuming product ID 1 exists)
        self.test_endpoint("GET", "/marketplace/products/1", "Get product details")
        
        # Farmer endpoints (require farmer auth)
        farmer_token = self.tokens.get("existing_farmer") or self.tokens.get("farmer")
        if farmer_token:
            self.print_info("\nTesting Farmer Endpoints...")
            headers = {"Authorization": f"Bearer {farmer_token}"}
            
            # Create product
            product_data = {
                "name": f"Test Tomatoes {int(time.time())}",
                "category": "crop",
                "description": "Fresh test tomatoes from our automated test farm. Very delicious!",
                "quantity": "50 baskets",
                "price": 2500,
                "discount_percentage": 10,
                "location": "Test Farm, Lagos",
                "images": ["https://example.com/tomato1.jpg", "https://example.com/tomato2.jpg"]
            }
            
            success, response = self.test_endpoint(
                "POST", "/marketplace/farmers/products",
                "Create new product",
                data=product_data,
                headers=headers,
                expected_status=[200, 201]
            )
            
            if success and response:
                product_id = response.json().get("id")
                if product_id:
                    self.created_resources["products"].append(product_id)
                    
                    # Update product
                    update_data = {"price": 2000, "description": "Updated description for testing"}
                    self.test_endpoint(
                        "PUT", f"/marketplace/farmers/products/{product_id}",
                        "Update product",
                        data=update_data,
                        headers=headers
                    )
                    
                    # Add discount
                    self.test_endpoint(
                        "POST", f"/marketplace/farmers/products/{product_id}/discount?discount_percentage=15",
                        "Add discount to product",
                        headers=headers
                    )
                    
                    # Remove discount
                    self.test_endpoint(
                        "DELETE", f"/marketplace/farmers/products/{product_id}/discount",
                        "Remove discount from product",
                        headers=headers
                    )
            
            # Get farmer's products
            self.test_endpoint(
                "GET", "/marketplace/farmers/products",
                "Get farmer's products",
                headers=headers
            )
            
            # Test product validation (should fail)
            invalid_products = [
                {
                    "name": "Invalid Product 1",
                    "category": "crop",
                    "description": "Too short",  # Less than 20 chars
                    "quantity": "5kg",
                    "price": 1000,
                    "location": "Test Farm",  # Added required field
                    "images": ["test.jpg"]
                },
                {
                    "name": "Invalid Product 2",
                    "category": "crop",
                    "description": "This is a valid description for the product",
                    "quantity": "5kg",
                    "price": 0,  # Invalid price
                    "location": "Test Farm",  # Added required field
                    "images": ["test.jpg"]
                }
            ]
            
            for i, invalid_product in enumerate(invalid_products, 1):
                self.test_endpoint(
                    "POST", "/marketplace/farmers/products",
                    f"Create invalid product {i} (should fail)",
                    data=invalid_product,
                    headers=headers,
                    expected_status=[400]
                )
        
        # Consumer endpoints
        consumer_token = self.tokens.get("existing_consumer") or self.tokens.get("consumer")
        if consumer_token and self.created_resources["products"]:
            self.print_info("\nTesting Consumer Endpoints...")
            headers = {"Authorization": f"Bearer {consumer_token}"}
            
            # Create order
            order_data = {
                "product_id": self.created_resources["products"][0],
                "quantity_ordered": "2 baskets",
                "delivery_address": "123 Test Street, Lagos"
            }
            
            success, response = self.test_endpoint(
                "POST", "/marketplace/orders",
                "Create order",
                data=order_data,
                headers=headers,
                expected_status=[200, 201]
            )
            
            if success and response:
                order_id = response.json().get("id")
                if order_id:
                    self.created_resources["orders"].append(order_id)
            
            # Create review
            if self.created_resources["products"]:
                review_data = {
                    "product_id": self.created_resources["products"][0],
                    "rating": 5,
                    "comment": "Excellent tomatoes!"
                }
                
                success, response = self.test_endpoint(
                    "POST", "/marketplace/reviews",
                    "Create review",
                    data=review_data,
                    headers=headers,
                    expected_status=[200, 201]
                )
                
                if success and response:
                    review_id = response.json().get("id")
                    if review_id:
                        self.created_resources["reviews"].append(review_id)
        
        # Get product reviews
        if self.created_resources["products"]:
            self.test_endpoint(
                "GET", f"/marketplace/products/{self.created_resources['products'][0]}/reviews",
                "Get product reviews"
            )
    
    def test_orders_endpoints(self):
        """Test all order management endpoints"""
        self.print_header("Testing Orders Endpoints")
        
        consumer_token = self.tokens.get("existing_consumer") or self.tokens.get("consumer")
        if not consumer_token:
            self.print_error("No consumer token available")
            return
        
        headers = {"Authorization": f"Bearer {consumer_token}"}
        
        # Get all orders
        success, response = self.test_endpoint(
            "GET", "/orders/",
            "Get all orders",
            headers=headers
        )
        
        if success and response:
            try:
                # Handle both dict and list responses
                response_data = response.json()
                if isinstance(response_data, dict):
                    orders = response_data.get("products", [])
                    # If no "products" key, check for "data" or similar
                    if not orders and "data" in response_data:
                        orders = response_data["data"]
                elif isinstance(response_data, list):
                    orders = response_data
                else:
                    orders = []
                
                if orders and len(orders) > 0:
                    order_id = orders[0].get("id")
                    
                    # Get order details
                    self.test_endpoint(
                        "GET", f"/orders/{order_id}",
                        "Get order details",
                        headers=headers
                    )
                    
                    # Get order timeline
                    self.test_endpoint(
                        "GET", f"/orders/{order_id}/timeline",
                        "Get order timeline",
                        headers=headers
                    )
                    
                    # Get order issues
                    self.test_endpoint(
                        "GET", f"/orders/{order_id}/issues",
                        "Get order issues",
                        headers=headers
                    )
                    
                    # Report issue (only for delivered orders)
                    if orders[0].get("status") in ["delivered", "awaiting_confirmation"]:
                        issue_data = {
                            "issue_description": "Test issue: Package was damaged during delivery"
                        }
                        self.test_endpoint(
                            "POST", f"/orders/{order_id}/report-issue",
                            "Report delivery issue",
                            data=issue_data,
                            headers=headers,
                            expected_status=[200, 201, 404]
                        )
                    
                    # Confirm delivery (only for awaiting confirmation)
                    if orders[0].get("status") == "awaiting_confirmation":
                        self.test_endpoint(
                            "POST", f"/orders/{order_id}/confirm-delivery",
                            "Confirm delivery",
                            headers=headers,
                            expected_status=[200, 404]
                        )
                else:
                    self.print_info("No orders found to test detailed endpoints")
            except Exception as e:
                self.print_error(f"Error processing orders response: {str(e)}")
        
        # Test with filters
        self.test_endpoint(
            "GET", "/orders/",
            "Get orders with status filter",
            params={"status": "delivered"},
            headers=headers
        )
        
        self.test_endpoint(
            "GET", "/orders/",
            "Get orders with search",
            params={"search": "tomato"},
            headers=headers
        )
        
        # Get order statistics
        self.test_endpoint(
            "GET", "/orders/statistics/summary",
            "Get order statistics",
            headers=headers
        )
    
    def cleanup(self):
        """Clean up created test resources"""
        self.print_header("Cleaning Up Test Resources")
        
        farmer_token = self.tokens.get("existing_farmer") or self.tokens.get("farmer")
        if farmer_token:
            headers = {"Authorization": f"Bearer {farmer_token}"}
            
            # Delete created products
            for product_id in self.created_resources["products"]:
                self.test_endpoint(
                    "DELETE", f"/marketplace/farmers/products/{product_id}",
                    f"Delete test product {product_id}",
                    headers=headers,
                    expected_status=[200, 204, 404]
                )
    
    def print_summary(self):
        """Print test summary"""
        self.print_header("Test Summary")
        
        passed = sum(1 for result, _ in self.test_results if result == "PASS")
        failed = sum(1 for result, _ in self.test_results if result == "FAIL")
        total = len(self.test_results)
        
        print(f"\nTotal Tests: {total}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        
        if failed > 0:
            print(f"\n{RED}Failed Tests:{RESET}")
            for result, description in self.test_results:
                if result == "FAIL":
                    print(f"  - {description}")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\n{BLUE}Success Rate: {success_rate:.1f}%{RESET}")
    
    def run_all_tests(self):
        """Run all API tests"""
        print(f"{BLUE}BigFarma API Comprehensive Test Suite{RESET}")
        print(f"{BLUE}Testing API at: {self.api_url}{RESET}")
        print(f"{BLUE}Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
        
        try:
            # Check server health first
            self.test_health()
            
            # Run all test suites
            self.test_auth_endpoints()
            self.test_user_endpoints()
            self.test_marketplace_endpoints()
            self.test_orders_endpoints()
            
            # Cleanup
            self.cleanup()
        except Exception as e:
            self.print_error(f"Test suite error: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Always print summary
            self.print_summary()


def main():
    """Main test runner"""
    print("Make sure the BigFarma server is running!")
    print("Start with: uvicorn main:app --reload")
    print("")
    input("Press Enter to start testing...")
    
    # Create tester instance
    tester = BigFarmaAPITester()
    
    try:
        # Run all tests
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
    
    print("\nTest run completed!")


if __name__ == "__main__":
    main()