import requests
import json

def test_add_product_endpoint():
    """
    Test the add_product endpoint directly to see if it's properly registered
    """
    url = "http://127.0.0.1:8000/api/products/families/add_product/"
    headers = {"Content-Type": "application/json"}
    data = {
        "family_id": "1",  # Use an actual family ID if available
        "product_id": "1"  # Use an actual product ID if available
    }
    
    print(f"Sending request to {url}")
    print(f"Headers: {headers}")
    print(f"Data: {json.dumps(data)}")
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 404:
            print("\nEndpoint not found. Checking URL configuration...")
            # Check list of available API endpoints
            api_root_response = requests.get("http://127.0.0.1:8000/api/products/")
            if api_root_response.status_code == 200:
                print("API root accessible. Available endpoints:")
                print(api_root_response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_add_product_endpoint()
