"""
Quick test to verify BigFarma API endpoints after refactoring
Focuses on testing that the removed endpoint is gone and new one works
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"

def quick_test():
    """Run a quick test of the refactored endpoints"""
    
    print("🔍 Quick BigFarma API Test")
    print("=" * 40)
    
    # Test credentials - using the same as in test_orders_api.py
    credentials = {
        "login": "jane.consumer@bigfarma.com",
        "password": "consumer123"
    }
    
    # 1. Check server health
    print("\n1. Checking server health...")
    try:
        health_response = requests.get("http://localhost:8000/health", timeout=3)
        if health_response.status_code == 200:
            print("✅ Server is running")
        else:
            print(f"⚠️  Server responded with: {health_response.status_code}")
    except requests.ConnectionError:
        print("❌ Server is not running!")
        print("   Start it with: uvicorn main:app --reload")
        return
    except Exception as e:
        print(f"❌ Error checking server: {e}")
        
    # 2. Login
    print("\n2. Testing login...")
    try:
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json=credentials,
            timeout=10
        )
        
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("✅ Login successful")
        else:
            print(f"❌ Login failed: {login_response.status_code}")
            print(f"   Response: {login_response.text}")
            return
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return
    
    # 3. Test removed endpoint
    print("\n3. Verifying old endpoint is removed...")
    try:
        old_response = requests.get(
            f"{BASE_URL}/marketplace/orders",
            headers=headers,
            timeout=5
        )
        
        if old_response.status_code == 404:
            print("✅ Old endpoint correctly removed (404)")
        elif old_response.status_code == 405:
            print("✅ GET method removed (405 - Method Not Allowed)")
            print("   POST still available for order creation")
        else:
            print(f"⚠️  Old endpoint returned: {old_response.status_code}")
            
    except Exception as e:
        print(f"⚠️  Error testing old endpoint: {e}")
    
    # 4. Test new endpoint
    print("\n4. Testing new orders endpoint...")
    try:
        new_response = requests.get(
            f"{BASE_URL}/orders/",
            headers=headers,
            timeout=10
        )
        
        if new_response.status_code == 200:
            orders = new_response.json()
            print(f"✅ New endpoint works! Found {len(orders)} orders")
            
            if orders and len(orders) > 0:
                # Show first order
                order = orders[0]
                print(f"\n   Sample order:")
                print(f"   - Order #: {order.get('order_number', 'N/A')}")
                print(f"   - Product: {order.get('product_name', 'N/A')}")
                print(f"   - Status: {order.get('status', 'N/A')}")
        else:
            print(f"❌ New endpoint failed: {new_response.status_code}")
            print(f"   Response: {new_response.text}")
            
    except Exception as e:
        print(f"❌ Error testing new endpoint: {e}")
    
    print("\n" + "=" * 40)
    print("✅ Refactoring test complete!")
    print("\nSummary:")
    print("- Marketplace GET /orders endpoint should be removed")
    print("- Orders GET / endpoint should work with enhanced features")
    print("- Order creation via POST /marketplace/orders remains unchanged")

if __name__ == "__main__":
    try:
        quick_test()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")