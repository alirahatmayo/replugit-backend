import requests

print("Testing manifest items API...")

try:
    response = requests.get('http://127.0.0.1:8000/api/manifests/items/')
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response type: {type(data)}")
        
        if isinstance(data, dict):
            print(f"Response keys: {list(data.keys())}")
            if 'results' in data:
                items = data['results']
                print(f"Found {len(items)} items")
                
                # Look for family mapped items
                mapped_items = [item for item in items if item.get('is_family_mapped')]
                print(f"Items with family mapping: {len(mapped_items)}")
                
                if mapped_items:
                    print("\nFamily mapped items:")
                    for item in mapped_items[:3]:
                        print(f"- ID: {item['id']}, Status: {item['status']}")
                        if item.get('mapped_family'):
                            print(f"  Family: {item['mapped_family']['name']}")
                        
                print(f"\nFirst 3 items (any status):")
                for item in items[:3]:
                    print(f"- ID: {item['id']}, Status: {item['status']}, Family Mapped: {item.get('is_family_mapped', False)}")
            
        print("\nSUCCESS: API is working correctly!")
                    
    else:
        print(f"Error response: {response.text}")
        
except Exception as e:
    print(f"Error: {e}")
