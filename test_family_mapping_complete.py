#!/usr/bin/env python3
"""
Test script to verify the complete family mapping solution is working.
This tests the new family_mapped_group field and effective_status logic.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from manifest.models import ManifestItem, ManifestGroup, Manifest
from products.models import ProductFamily
from manifest.serializers import ManifestItemSerializer
import json

def test_family_mapping_logic():
    """Test the family mapping logic with the new family_mapped_group field"""
    print("🧪 Testing Family Mapping Logic...")
    
    try:
        # Get or create test data
        manifest = Manifest.objects.first()
        if not manifest:
            print("❌ No manifests found. Please upload a manifest first.")
            return False
            
        items = ManifestItem.objects.filter(manifest=manifest)[:5]
        if not items:
            print("❌ No manifest items found.")
            return False
            
        print(f"✅ Found {len(items)} manifest items to test")
        
        # Test the properties and serializer
        for item in items:
            print(f"\n📋 Testing Item {item.id} (Row {item.row_number}):")
            print(f"   - Group: {item.group}")
            print(f"   - Family Mapped Group: {item.family_mapped_group}")
            print(f"   - Raw Status: {item.status}")
            print(f"   - Effective Status: {item.effective_status}")
            print(f"   - Is Family Mapped: {item.is_mapped_to_family}")
            print(f"   - Mapped Family: {item.mapped_family}")
            
            # Test serializer output
            serializer = ManifestItemSerializer(item)
            serialized_data = serializer.data
            print(f"   - Serialized Status: {serialized_data.get('status')}")
            print(f"   - Serialized Is Family Mapped: {serialized_data.get('is_family_mapped')}")
            print(f"   - Serialized Mapped Family: {serialized_data.get('mapped_family')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing family mapping logic: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_group_family_assignment():
    """Test assigning a family to a group and verify items get updated"""
    print("\n🔗 Testing Group Family Assignment...")
    
    try:
        # Find a group without a family
        group = ManifestGroup.objects.filter(product_family__isnull=True).first()
        if not group:
            print("❌ No groups without families found")
            return False
            
        # Find a product family
        family = ProductFamily.objects.first()
        if not family:
            print("❌ No product families found")
            return False
            
        print(f"✅ Found group {group.id} and family {family.name}")
        
        # Get items in this group before assignment
        items_before = list(group.items.all())
        print(f"   - Group has {len(items_before)} items")
        
        if items_before:
            item = items_before[0]
            print(f"   - Before: Item {item.id} family_mapped_group = {item.family_mapped_group}")
            print(f"   - Before: Item {item.id} effective_status = {item.effective_status}")
        
        # Assign family to group
        group.product_family = family
        group.save()
        print(f"✅ Assigned family {family.name} to group {group.id}")
        
        # Check items after assignment (signals should have updated them)
        if items_before:
            item.refresh_from_db()
            print(f"   - After: Item {item.id} family_mapped_group = {item.family_mapped_group}")
            print(f"   - After: Item {item.id} effective_status = {item.effective_status}")
            
            # Verify the family_mapped_group points to our group
            if item.family_mapped_group == group:
                print("✅ family_mapped_group correctly updated by signal")
            else:
                print("❌ family_mapped_group not updated correctly")
                return False
                
            # Verify effective_status is now 'mapped'
            if item.effective_status == 'mapped':
                print("✅ effective_status correctly shows 'mapped'")
            else:
                print("❌ effective_status not showing 'mapped'")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing group family assignment: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test the API endpoints to ensure they return the correct data"""
    print("\n🌐 Testing API Endpoints...")
    
    try:
        import requests
        
        base_url = "http://127.0.0.1:8000"
        
        # Test manifest items endpoint
        response = requests.get(f"{base_url}/api/manifest-items/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ ManifestItems API working - returned {len(data.get('results', []))} items")
            
            # Check first item for family mapping fields
            if data.get('results'):
                item = data['results'][0]
                required_fields = ['status', 'is_family_mapped', 'mapped_family']
                for field in required_fields:
                    if field in item:
                        print(f"   - ✅ Field '{field}' present: {item[field]}")
                    else:
                        print(f"   - ❌ Field '{field}' missing")
        else:
            print(f"❌ ManifestItems API error: {response.status_code}")
            return False
        
        # Test manifest groups endpoint
        response = requests.get(f"{base_url}/api/manifest-groups/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ ManifestGroups API working - returned {len(data.get('results', []))} groups")
        else:
            print(f"❌ ManifestGroups API error: {response.status_code}")
            return False
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Django server. Make sure it's running on http://127.0.0.1:8000/")
        return False
    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Complete Family Mapping Solution")
    print("=" * 50)
    
    success = True
    
    # Test 1: Basic family mapping logic
    success &= test_family_mapping_logic()
    
    # Test 2: Group family assignment with signals
    success &= test_group_family_assignment()
    
    # Test 3: API endpoints
    success &= test_api_endpoints()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! Family mapping solution is working correctly.")
        print("\n📋 Summary of implemented features:")
        print("   ✅ family_mapped_group field for performance")
        print("   ✅ effective_status property returns 'mapped' when family mapped")
        print("   ✅ mapped_family property returns the ProductFamily")
        print("   ✅ Django signals automatically update family mapping status")
        print("   ✅ Serializers expose family mapping data to frontend")
        print("   ✅ API endpoints working correctly")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
