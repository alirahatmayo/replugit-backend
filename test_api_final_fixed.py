#!/usr/bin/env python3
"""
Final test of the family mapping API endpoint
"""

import requests
import json

def test_manifest_items_api():
    print('🚀 Starting family mapping API test...')
    try:
        # Test the API endpoint
        url = 'http://127.0.0.1:8000/api/manifests/items/?format=json'
        print(f'📡 Making request to: {url}')
        response = requests.get(url)
        
        print(f'✅ API Response Status: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            print(f'🔍 Response type: {type(data)}')
            
            # Handle both paginated and direct list responses
            if isinstance(data, list):
                items = data
                total_count = len(data)
            elif isinstance(data, dict) and 'results' in data:
                items = data['results']
                total_count = data.get('count', len(items))
            else:
                print(f'❌ Unexpected response format: {type(data)}')
                return
                
            print(f'📊 Total items: {total_count}')
            
            if items:
                print('\n🔍 Sample items with family mapping:')
                
                # Find items with family mapping
                family_mapped_items = [item for item in items if item.get('is_family_mapped')]
                
                if family_mapped_items:
                    for i, item in enumerate(family_mapped_items[:3]):
                        print(f'\nItem {i+1}:')
                        print(f'  - ID: {item.get("id")}')
                        print(f'  - Status: {item.get("status")}')
                        print(f'  - Family Mapped: {item.get("is_family_mapped")}')
                        if item.get('mapped_family'):
                            family = item['mapped_family']
                            print(f'  - Mapped Family: {family.get("name", "N/A")}')
                            print(f'  - Family SKU: {family.get("sku", "N/A")}')
                        else:
                            print('  - No family mapping data')
                else:
                    print('❌ No items with family mapping found in response')
                    # Show a few regular items for debugging
                    print('\n🔍 First few regular items:')
                    for i, item in enumerate(items[:3]):
                        print(f'  Item {i+1}: ID={item.get("id")}, Status={item.get("status")}, Family Mapped={item.get("is_family_mapped")}')
                    
                print(f'\n📈 Family mapping statistics:')
                mapped_count = sum(1 for item in items if item.get('is_family_mapped'))
                print(f'  - Items with family mapping: {mapped_count}/{len(items)}')
                
            else:
                print('❌ No items found in API response')
        else:
            print(f'❌ API request failed: {response.text}')
            
    except Exception as e:
        print(f'❌ Error testing API: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_manifest_items_api()
