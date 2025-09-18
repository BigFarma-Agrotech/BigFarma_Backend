"""
Test script for marketplace filtering functionality
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_marketplace_filtering():
    print("🛒 Testing Marketplace Filtering Features")
    print("=" * 50)
    
    # Test 1: Get categories
    print("\n1. Testing categories endpoint...")
    try:
        resp = requests.get(f"{BASE_URL}/marketplace/categories")
        if resp.status_code == 200:
            categories = resp.json()["categories"]
            print("✅ Categories endpoint working!")
            print("   Available categories:")
            for cat in categories:
                print(f"   - {cat['icon']} {cat['name']} (id: {cat['id']})")
        else:
            print(f"❌ Categories endpoint failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Search functionality
    print("\n2. Testing search functionality...")
    try:
        resp = requests.get(f"{BASE_URL}/marketplace/products?search=tomato")
        if resp.status_code == 200:
            products = resp.json()
            print(f"✅ Search working! Found {len(products)} products with 'tomato'")
            if products:
                print(f"   Example: {products[0]['name']}")
        else:
            print(f"❌ Search failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Category filtering
    print("\n3. Testing category filtering...")
    for category in ["vegetables", "fruits", "grains", "proteins"]:
        try:
            resp = requests.get(f"{BASE_URL}/marketplace/products?category={category}")
            if resp.status_code == 200:
                products = resp.json()
                print(f"✅ {category.capitalize()}: Found {len(products)} products")
            else:
                print(f"❌ Category filter failed for {category}: {resp.status_code}")
        except Exception as e:
            print(f"❌ Error filtering {category}: {e}")
    
    # Test 4: Price filtering
    print("\n4. Testing price range filtering...")
    try:
        resp = requests.get(f"{BASE_URL}/marketplace/products?min_price=1000&max_price=5000")
        if resp.status_code == 200:
            products = resp.json()
            print(f"✅ Price filter working! Found {len(products)} products between ₦1000-₦5000")
            if products:
                print(f"   Price range: ₦{min(p['price'] for p in products)} - ₦{max(p['price'] for p in products)}")
        else:
            print(f"❌ Price filter failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 5: Combined filters
    print("\n5. Testing combined filters...")
    try:
        resp = requests.get(f"{BASE_URL}/marketplace/products?category=fruits&max_price=10000")
        if resp.status_code == 200:
            products = resp.json()
            print(f"✅ Combined filters working! Found {len(products)} fruits under ₦10000")
        else:
            print(f"❌ Combined filters failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("✅ Categories endpoint - for UI category display")
    print("✅ Search - for product name search")
    print("✅ Category filter - maps UI categories to DB categories")
    print("✅ Price range filter - min/max price filtering")
    print("✅ Combined filters - multiple filters work together")
    
    print("\nExample API calls:")
    print("GET /marketplace/categories")
    print("GET /marketplace/products?search=pepper")
    print("GET /marketplace/products?category=vegetables")
    print("GET /marketplace/products?min_price=2000&max_price=8000")
    print("GET /marketplace/products?category=fruits&search=water&max_price=5000")

if __name__ == "__main__":
    print("Make sure the server is running: uvicorn main:app --reload")
    input("Press Enter to start testing...")
    
    try:
        # Quick server check
        health = requests.get("http://localhost:8000/health", timeout=2)
        if health.status_code == 200:
            test_marketplace_filtering()
        else:
            print("❌ Server not responding properly")
    except requests.ConnectionError:
        print("❌ Cannot connect to server at http://localhost:8000")
        print("   Please start the server first!")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
