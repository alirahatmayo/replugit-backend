#!/usr/bin/env python
"""
Test script to verify the family mapping fix for ManifestGroup serializer.
This script will test that the ManifestGroup API returns the family data 
with the correct field names that the frontend expects.
"""

import os
import sys
import django
from django.test import Client
from django.urls import reverse
import json

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from manifest.models import ManifestGroup
from products.models import ProductFamily
from manifest.serializers import ManifestGroupSerializer

def test_manifest_group_serializer():
    """Test that ManifestGroupSerializer includes family data correctly"""
    print("Testing ManifestGroupSerializer...")
    
    # Check if we have any manifest groups
    groups = ManifestGroup.objects.all()
    if not groups.exists():
        print("No manifest groups found in database")
        return False
    
    # Test serializer with a group that has a product_family
    group_with_family = groups.filter(product_family__isnull=False).first()
    if group_with_family:
        print(f"Testing group with family: {group_with_family.id}")
        serializer = ManifestGroupSerializer(group_with_family)
        data = serializer.data
        
        # Check if 'family' field is present
        if 'family' in data:
            print("✓ 'family' field is present in serialized data")
            print(f"  Family data: {data['family']}")
        else:
            print("✗ 'family' field is missing from serialized data")
            return False
            
        # Check if 'family_mappings' field is present
        if 'family_mappings' in data:
            print("✓ 'family_mappings' field is present in serialized data")
            print(f"  Family mappings: {data['family_mappings']}")
        else:
            print("✗ 'family_mappings' field is missing from serialized data")
            return False
    else:
        print("No manifest groups with product families found")
        # Test with a group without family
        group_without_family = groups.first()
        serializer = ManifestGroupSerializer(group_without_family)
        data = serializer.data
        
        print(f"Testing group without family: {group_without_family.id}")
        if 'family' in data and data['family'] is None:
            print("✓ 'family' field is present and None for groups without families")
        else:
            print("✗ 'family' field behavior incorrect for groups without families")
            
        if 'family_mappings' in data and data['family_mappings'] == []:
            print("✓ 'family_mappings' field is present and empty for groups without families")
        else:
            print("✗ 'family_mappings' field behavior incorrect for groups without families")
    
    return True

def test_api_endpoint():
    """Test the API endpoint directly"""
    print("\nTesting API endpoint...")
    
    client = Client()
    
    # Test the manifest groups list endpoint
    try:
        response = client.get('/api/manifests/groups/')
        
        if response.status_code == 200:
            print("✓ API endpoint accessible")
            data = response.json()
            
            if 'results' in data:
                results = data['results']
            else:
                results = data
                
            if results:
                first_group = results[0]
                print(f"First group data keys: {list(first_group.keys())}")
                
                if 'family' in first_group:
                    print("✓ 'family' field present in API response")
                    print(f"  Family value: {first_group['family']}")
                else:
                    print("✗ 'family' field missing from API response")
                    
                if 'family_mappings' in first_group:
                    print("✓ 'family_mappings' field present in API response")
                    print(f"  Family mappings value: {first_group['family_mappings']}")
                else:
                    print("✗ 'family_mappings' field missing from API response")
            else:
                print("No groups returned from API")
        else:
            print(f"✗ API endpoint returned status {response.status_code}")
            print(f"Response: {response.content}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing API endpoint: {e}")
        return False
    
    return True

def show_database_stats():
    """Show some database statistics"""
    print("\nDatabase Statistics:")
    
    total_groups = ManifestGroup.objects.count()
    groups_with_families = ManifestGroup.objects.filter(product_family__isnull=False).count()
    total_families = ProductFamily.objects.count()
    
    print(f"Total manifest groups: {total_groups}")
    print(f"Groups with product families: {groups_with_families}")
    print(f"Total product families: {total_families}")
    
    if groups_with_families > 0:
        sample_group = ManifestGroup.objects.filter(product_family__isnull=False).first()
        print(f"Sample group with family: ID {sample_group.id}, Family: {sample_group.product_family.name}")

if __name__ == "__main__":
    print("Family Mapping Fix Test")
    print("=" * 50)
    
    show_database_stats()
    
    success = True
    success &= test_manifest_group_serializer()
    success &= test_api_endpoint()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ All tests passed! Family mapping fix appears to be working.")
    else:
        print("✗ Some tests failed. Check the output above.")
    
    sys.exit(0 if success else 1)
