"""
BigFarma Orders API Testing Script
This script demonstrates how to test the Orders API endpoints
"""
import requests
import json
from typing import Optional
import sys

class BigFarmaOrdersAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.headers = {"Content-Type": "application/json"}
        
    def check_server_connection(self) -> bool:
        """Check if server is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Server is running at {self.base_url}")
                return True
            else:
                print(f"⚠️ Server responded with status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to server at {self.base_url}")
            print("   Make sure the server is running with: uvicorn main:app --reload")
            return False
        except Exception as e:
            print(f"❌ Server connection error: {e}")
            return False
        
    def login(self, email: str, password: str) -> bool:
        """Login and get access token"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                headers=self.headers,
                json={
                    "login": email,
                    "password": password
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.headers["Authorization"] = f"Bearer {self.access_token}"
                print(f"✅ Login successful for {email}")
                return True
            elif response.status_code == 401:
                print(f"❌ Login failed: Invalid credentials for {email}")
                print("   Make sure sample data has been created with: python create_sample_data.py")
                return False
            else:
                print(f"❌ Login failed: {response.json()}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection error during login. Is the server running?")
            return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def get_my_orders(self, status_filter: str = None, search: str = None):
        """Get all orders for the logged-in user"""
        try:
            params = {}
            if status_filter:
                params["status"] = status_filter
            if search:
                params["search"] = search
                
            response = requests.get(
                f"{self.base_url}/api/v1/orders/",
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                orders = response.json()
                print(f"\n📦 Found {len(orders)} orders:")
                for order in orders:
                    status_emoji = {
                        "pending": "⏳",
                        "confirmed": "✅", 
                        "shipping": "🚚",
                        "awaiting_confirmation": "⏰",
                        "delivered": "📦",
                        "cancelled": "❌",
                        "delivery_issue": "⚠️"
                    }
                    emoji = status_emoji.get(order["status"], "📋")
                    print(f"   {emoji} Order #{order['order_number']} - {order['product_name']} ({order['status']})")
                    print(f"      Farm: {order['farm_name']} | Total: ₦{order['total_price']:,.2f}")
                
                return orders
            else:
                print(f"❌ Failed to get orders: {response.json()}")
                return []
        except Exception as e:
            print(f"❌ Error getting orders: {e}")
            return []
    
    def get_order_details(self, order_id: int):
        """Get detailed information about a specific order"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/orders/{order_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                order = response.json()
                print(f"\n📋 Order Details for #{order['order_number']}:")
                print(f"   Product: {order['product_name']}")
                print(f"   Farm: {order['farm_name']} by {order['farmer_name']}")
                print(f"   Status: {order['status']}")
                print(f"   Quantity: {order['quantity_ordered']}")
                print(f"   Total: ₦{order['total_price']:,.2f}")
                print(f"   Delivery: {order['delivery_address']}")
                print(f"   Contact: {order.get('contact_phone', 'N/A')}")
                
                print(f"\n📅 Order Timeline ({len(order['timeline'])} entries):")
                for timeline in order['timeline']:
                    status_icon = "✅" if timeline['is_completed'] else "⏳"
                    print(f"   {status_icon} {timeline['title']}")
                    print(f"      {timeline['description']}")
                    if timeline['completed_at']:
                        print(f"      Completed: {timeline['completed_at'][:19]}")
                    print()
                
                if order['issues']:
                    print(f"\n⚠️ Issues Reported ({len(order['issues'])} issues):")
                    for issue in order['issues']:
                        print(f"   Status: {issue['status']}")
                        print(f"   Description: {issue['issue_description']}")
                        if issue['admin_response']:
                            print(f"   Response: {issue['admin_response']}")
                        print()
                
                return order
            else:
                print(f"❌ Failed to get order details: {response.json()}")
                return None
        except Exception as e:
            print(f"❌ Error getting order details: {e}")
            return None
    
    def report_delivery_issue(self, order_id: int, issue_description: str):
        """Report a delivery issue for an order"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/orders/{order_id}/report-issue",
                headers=self.headers,
                json={
                    "issue_description": issue_description
                }
            )
            
            if response.status_code == 200:
                issue = response.json()
                print(f"✅ Issue reported successfully for order {order_id}")
                print(f"   Issue ID: {issue['id']}")
                print(f"   Status: {issue['status']}")
                return issue
            else:
                print(f"❌ Failed to report issue: {response.json()}")
                return None
        except Exception as e:
            print(f"❌ Error reporting issue: {e}")
            return None
    
    def confirm_delivery(self, order_id: int):
        """Confirm delivery of an order"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/orders/{order_id}/confirm-delivery",
                headers=self.headers
            )
            
            if response.status_code == 200:
                order = response.json()
                print(f"✅ Delivery confirmed for order #{order['order_number']}")
                print(f"   Status: {order['status']}")
                print(f"   Thank you! The farmer has been notified.")
                return order
            else:
                print(f"❌ Failed to confirm delivery: {response.json()}")
                return None
        except Exception as e:
            print(f"❌ Error confirming delivery: {e}")
            return None
    
    def get_order_statistics(self):
        """Get order statistics for the user"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/orders/statistics/summary",
                headers=self.headers
            )
            
            if response.status_code == 200:
                stats = response.json()["data"]
                print(f"\n📊 Order Statistics:")
                print(f"   Total Orders: {stats['total_orders']}")
                print(f"   Pending: {stats['pending_orders']}")
                print(f"   Delivered: {stats['delivered_orders']}")
                print(f"   Cancelled: {stats['cancelled_orders']}")
                print(f"   Total Spent: ₦{stats['total_spent']:,.2f}")
                print(f"   Average Order Value: ₦{stats['average_order_value']:,.2f}")
                return stats
            else:
                print(f"❌ Failed to get statistics: {response.json()}")
                return None
        except Exception as e:
            print(f"❌ Error getting statistics: {e}")
            return None

def run_comprehensive_test():
    """Run a comprehensive test of the Orders API"""
    print("🚀 BigFarma Orders API Testing")
    print("=" * 50)
    
    tester = BigFarmaOrdersAPITester()
    
    # Check server connection first
    if not tester.check_server_connection():
        print("\n💡 To start the server, run:")
        print("   cd C:\\Users\\okoro\\Data\\other\\AltSchool\\BigFarma_Backend")
        print("   uvicorn main:app --reload")
        return
    
    # Test with consumer account
    consumer_email = "jane.consumer@bigfarma.com"
    consumer_password = "consumer123"
    
    print(f"\n1️⃣ Testing login with consumer account...")
    if not tester.login(consumer_email, consumer_password):
        print("\n💡 If login fails, create sample data first:")
        print("   python create_sample_data.py")
        return
    
    print(f"\n2️⃣ Getting all orders...")
    orders = tester.get_my_orders()
    
    if orders:
        # Test with the first order
        first_order = orders[0]
        order_id = first_order["id"]
        
        print(f"\n3️⃣ Getting detailed info for Order #{order_id}...")
        tester.get_order_details(order_id)
        
        print(f"\n4️⃣ Testing order filtering by status...")
        tester.get_my_orders(status_filter="delivered")
        
        print(f"\n5️⃣ Testing order search...")
        tester.get_my_orders(search="tomato")
        
        print(f"\n6️⃣ Getting order statistics...")
        tester.get_order_statistics()
        
        # Test delivery confirmation for awaiting_confirmation orders
        awaiting_orders = [o for o in orders if o["status"] == "awaiting_confirmation"]
        if awaiting_orders:
            print(f"\n7️⃣ Testing delivery confirmation...")
            tester.confirm_delivery(awaiting_orders[0]["id"])
        
        # Test issue reporting for a delivered/shipping order
        suitable_orders = [o for o in orders if o["status"] in ["delivered", "shipping", "awaiting_confirmation"]]
        if suitable_orders:
            print(f"\n8️⃣ Testing issue reporting...")
            tester.report_delivery_issue(
                suitable_orders[0]["id"],
                "Package was damaged during delivery. Some items were missing."
            )
    else:
        print("⚠️ No orders found. Make sure sample data has been created.")
        print("   Run: python create_sample_data.py")
    
    print(f"\n✅ Comprehensive API testing completed!")
    print(f"\n💡 Tips:")
    print(f"   - Use different consumer accounts to see different order data")
    print(f"   - Try filtering and searching with various parameters") 
    print(f"   - Test the API with various order statuses")

def run_quick_test():
    """Run a quick test to verify API is working"""
    print("⚡ Quick API Test")
    print("=" * 30)
    
    tester = BigFarmaOrdersAPITester()
    
    # Check server connection
    if not tester.check_server_connection():
        return
    
    # Quick login test
    if tester.login("jane.consumer@bigfarma.com", "consumer123"):
        orders = tester.get_my_orders()
        if orders:
            print(f"✅ API is working! Found {len(orders)} orders.")
            print(f"\nDatabase Connection: ✅ PostgreSQL")
            print(f"Authentication: ✅ JWT Working")
            print(f"Orders API: ✅ Functional")
        else:
            print("⚠️ API working but no orders found.")
            print("   Create sample data with: python create_sample_data.py")
    else:
        print("❌ API test failed.")
        print("   Check if sample data exists: python create_sample_data.py")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        run_quick_test()
    else:
        run_comprehensive_test()