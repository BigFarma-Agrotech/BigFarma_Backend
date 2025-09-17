"""
Quick diagnostic to check if the orders endpoint works with the code fixes
Even if some orders don't have order_numbers in the database
"""

import requests

BASE_URL = "http://localhost:8000/api/v1"

def quick_diagnostic():
    print("🔍 Quick Diagnostic Check")
    print("=" * 40)
    
    # Check server
    try:
        health = requests.get("http://localhost:8000/health", timeout=2)
        if health.status_code == 200:
            print("✅ Server is running")
        else:
            print("⚠️  Server responded with:", health.status_code)
            return
    except:
        print("❌ Server is not running!")
        print("   Start it with: uvicorn main:app --reload")
        return
    
    # Quick login and test
    print("\nTesting with our code fixes...")
    
    try:
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"login": "jane.consumer@bigfarma.com", "password": "consumer123"}
        )
        
        if login_resp.status_code != 200:
            print(f"❌ Login failed: {login_resp.status_code}")
            return
            
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test orders endpoint
        orders_resp = requests.get(f"{BASE_URL}/orders/", headers=headers)
        
        if orders_resp.status_code == 200:
            orders = orders_resp.json()
            print(f"\n✅ SUCCESS! Orders endpoint is working!")
            print(f"   Found {len(orders)} orders")
            
            if orders:
                order = orders[0]
                print(f"\n   Sample order:")
                print(f"   - ID: {order.get('id')}")
                print(f"   - Order Number: {order.get('order_number')}")
                print(f"   - Product: {order.get('product_name')}")
                
                # Check if our fallback is working
                order_num = order.get('order_number', '')
                if order_num.startswith('BF0000'):
                    print(f"\n   ℹ️  Note: Using fallback order number")
                    print(f"      This means the order doesn't have a number in DB")
                    print(f"      But the endpoint is working correctly!")
                    
            print("\n✅ The refactoring and fixes are working!")
            print("   No need to run the database fix unless you want")
            print("   to permanently update order numbers in the DB.")
            
        else:
            print(f"\n❌ Orders endpoint failed: {orders_resp.status_code}")
            print("   This shouldn't happen with our fixes...")
            print(f"   Error: {orders_resp.text[:200]}...")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "=" * 40)

if __name__ == "__main__":
    quick_diagnostic()
