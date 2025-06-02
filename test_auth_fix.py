#!/usr/bin/env python3
"""
Test the receipt batch creation API with our authentication fix
"""
import requests
import json

def test_receipt_batch_creation():
    """Test creating a receipt batch through the API"""
    
    # API endpoint
    url = "http://localhost:8000/api/receiving/batches/"
    
    # Test data for receipt batch creation
    test_data = {
        "location": 1,  # Assuming location ID 1 exists
        "notes": "Test batch from authentication fix",
        "items": [
            {
                "product_family": 1,  # Using product_family instead of product
                "quantity": 5,
                "unit_cost": 25.99,
                "notes": "Test item with family mapping",
                "requires_unit_qc": False,
                "create_product_units": True
            }
        ]
    }
    
    print("🧪 Testing receipt batch creation API...")
    print(f"URL: {url}")
    print(f"Data: {json.dumps(test_data, indent=2)}")
    
    try:
        # Make the API request
        response = requests.post(url, json=test_data)
        
        print(f"\n📊 Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 201:
            print("✅ SUCCESS: Receipt batch created successfully!")
            print("Response Data:", json.dumps(response.json(), indent=2))
            return True
        else:
            print("❌ FAILED: Receipt batch creation failed")
            print("Response Data:", response.text)
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to backend server")
        print("Make sure the Django server is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_simple_endpoint():
    """Test a simple endpoint to verify server is running"""
    try:
        response = requests.get("http://localhost:8000/api/")
        print(f"✅ Server is running - Status: {response.status_code}")
        return True
    except:
        print("❌ Server is not responding")
        return False

if __name__ == "__main__":
    print("🔧 TESTING AUTHENTICATION FIX")
    print("=" * 40)
    
    # First check if server is running
    if test_simple_endpoint():
        print()
        test_receipt_batch_creation()
    else:
        print("Please start the Django backend server first")
