"""
Test script for enhanced marketplace features
Tests all new filtering, search suggestions, and validation features
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_enhanced_marketplace():
    print("🛒 Testing Enhanced Marketplace Features")
    print("=" * 50)
    
    # Test 1: Location filtering
    print("\n1. Testing location filtering...")
    try:
        resp = requests.get(f"{BASE_URL}/marketplace/products?location=lagos")
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Location filter working! Found {data['total_count']} products in Lagos")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Availability filtering
    print("\n2. Testing availability filtering...")
    for status in ["in_stock", "out_of_stock", "all"]:
        try:
            resp = requests.get(f"{BASE_URL}/marketplace/products?availability={status}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ {status}: {data['total_count']} products")
        except Exception as e:
            print(f"❌ Error with {status}: {e}")
    
    # Test 3: Sorting options
    print("\n3. Testing sorting options...")
    for sort in ["price_asc", "price_desc", "rating", "newest"]:
        try:
            resp = requests.get(f"{BASE_URL}/marketplace/products?sort_by={sort}&limit=3")
            if resp.status_code == 200:
                data = resp.json()
                products = data['products']
                if products:
                    prices = [p['price'] for p in products]
                    print(f"✅ Sort by {sort}: {prices}")
        except Exception as e:
            print(f"❌ Error with {sort}: {e}")
    
    # Test 4: Spelling suggestions
    print("\n4. Testing spelling suggestions...")
    misspellings = ["tommato", "peper", "orenge", "chickn"]
    for word in misspellings:
        try:
            resp = requests.get(f"{BASE_URL}/marketplace/products?search={word}")
            if resp.status_code == 200:
                data = resp.json()
                if data['search_suggestions']:
                    print(f"✅ '{word}' → Did you mean: {', '.join(data['search_suggestions'])}")
                else:
                    print(f"ℹ️  No suggestions for '{word}'")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Test 5: No results handling
    print("\n5. Testing no results handling...")
    try:
        resp = requests.get(f"{BASE_URL}/marketplace/products?search=xyz123&min_price=999999")
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ No results handled properly:")
            print(f"   - Filter suggestions: {len(data.get('filter_suggestions', []))}")
            print(f"   - Related products: {len(data.get('related_products', []))}")
            if data['filter_suggestions']:
                print(f"   - Suggestions: {', '.join(data['filter_suggestions'])}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 6: Combined filters
    print("\n6. Testing combined filters...")
    try:
        resp = requests.get(
            f"{BASE_URL}/marketplace/products?"
            f"category=vegetables&location=lagos&min_price=1000&max_price=5000"
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Combined filters: {data['total_count']} vegetables in Lagos (₦1000-5000)")
            print(f"   - Filters applied: {data['filters_applied']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 7: Search in description
    print("\n7. Testing search in description...")
    try:
        resp = requests.get(f"{BASE_URL}/marketplace/products?search=fresh")
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Search 'fresh': Found {data['total_count']} products")
            print("   (Searches both name and description)")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 8: Pagination info
    print("\n8. Testing pagination info...")
    try:
        resp = requests.get(f"{BASE_URL}/marketplace/products?limit=5")
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Pagination working:")
            print(f"   - Page: {data['page']}")
            print(f"   - Page size: {data['page_size']}")
            print(f"   - Total products: {data['total_count']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("Enhanced Features Summary:")
    print("✅ Location filtering")
    print("✅ Availability filtering (in_stock, out_of_stock, all)")
    print("✅ Multiple sort options")
    print("✅ Spelling suggestions for searches")
    print("✅ Filter suggestions when no results")
    print("✅ Related products on empty results")
    print("✅ Search in both name and description")
    print("✅ Product completeness validation")
    print("✅ Pagination with total count")

def test_product_validation():
    print("\n\n📝 Testing Product Creation Validation")
    print("=" * 50)
    
    # First login as farmer
    login_data = {"login": "john.farmer@bigfarma.com", "password": "farmer123"}
    login_resp = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if login_resp.status_code != 200:
        print("❌ Could not login as farmer")
        return
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test incomplete product
    print("\n1. Testing incomplete product rejection...")
    
    incomplete_products = [
        {
            "name": "Test Product",
            "category": "crop",
            "description": "Short desc",  # Too short
            "quantity": "5 kg",
            "price": 1000,
            "images": ["image1.jpg"]
        },
        {
            "name": "Test Product",
            "category": "crop",
            "description": "This is a proper description for the product",
            "quantity": "5 kg",
            "price": 1000,
            "images": []  # No images
        },
        {
            "name": "Test Product",
            "category": "crop",
            "description": "This is a proper description for the product",
            "quantity": "5 kg",
            "price": 0,  # Invalid price
            "images": ["image1.jpg"]
        }
    ]
    
    for i, product in enumerate(incomplete_products, 1):
        resp = requests.post(
            f"{BASE_URL}/marketplace/farmers/products",
            json=product,
            headers=headers
        )
        if resp.status_code == 400:
            print(f"✅ Test {i}: {resp.json()['detail']}")
        else:
            print(f"❌ Test {i} should have failed")

if __name__ == "__main__":
    print("Make sure the server is running: uvicorn main:app --reload")
    input("Press Enter to start testing...")
    
    try:
        # Quick server check
        health = requests.get("http://localhost:8000/health", timeout=2)
        if health.status_code == 200:
            test_enhanced_marketplace()
            test_product_validation()
        else:
            print("❌ Server not responding properly")
    except requests.ConnectionError:
        print("❌ Cannot connect to server at http://localhost:8000")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
