#!/usr/bin/env python3
"""
Test script for family mapping API endpoints
"""
import requests
import json

def test_manifest_groups():
    """Test the manifest groups endpoint"""
    try:
        response = requests.get('http://localhost:8000/api/manifests/groups/')
        print(f'GET /api/manifests/groups/ Status: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            groups = data.get('results', data) if isinstance(data, dict) else data
            print(f'Groups found: {len(groups)}')
            
            if groups:
                first_group = groups[0]
                print(f'First group ID: {first_group.get("id")}')
                print(f'First group product_family: {first_group.get("product_family")}')
                return first_group.get("id")
        else:
            print(f'Error response: {response.text}')
            return None
            
    except Exception as e:
        print(f'Error: {e}')
        return None

def test_patch_group(group_id, family_id=1):
    """Test patching a group with a product family"""
    if not group_id:
        print("No group ID available for testing")
        return
        
    try:
        payload = {'product_family': family_id}
        response = requests.patch(
            f'http://localhost:8000/api/manifests/groups/{group_id}/',
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f'PATCH /api/manifests/groups/{group_id}/ Status: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            print(f'Updated group product_family: {data.get("product_family")}')
        else:
            print(f'Error response: {response.text}')
            
    except Exception as e:
        print(f'Error: {e}')

def test_product_families():
    """Test the product families endpoint"""
    try:
        response = requests.get('http://localhost:8000/api/products/families/')
        print(f'GET /api/products/families/ Status: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            families = data.get('results', data) if isinstance(data, dict) else data
            print(f'Product families found: {len(families)}')
            
            if families:
                first_family = families[0]
                print(f'First family ID: {first_family.get("id")}')
                print(f'First family name: {first_family.get("name")}')
        else:
            print(f'Error response: {response.text}')
            
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    print("Testing family mapping API endpoints...")
    print("=" * 50)
    
    # Test product families endpoint
    print("\n1. Testing product families endpoint:")
    test_product_families()
    
    # Test manifest groups endpoint
    print("\n2. Testing manifest groups endpoint:")
    group_id = test_manifest_groups()
    
    # Test patching a group
    if group_id:
        print(f"\n3. Testing PATCH on group {group_id}:")
        test_patch_group(group_id)
    
    print("\nAPI endpoint testing complete!")
