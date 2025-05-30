#!/usr/bin/env python
"""
Simple test to verify ManifestGroup serializer works correctly
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from manifest.models import ManifestGroup
from manifest.serializers import ManifestGroupSerializer

def test_serializer():
    print("Testing ManifestGroupSerializer...")
    
    # Get total count
    total_groups = ManifestGroup.objects.count()
    print(f"Total ManifestGroups in database: {total_groups}")
    
    if total_groups == 0:
        print("❌ No manifest groups found to test")
        return False
    
    # Get first group
    first_group = ManifestGroup.objects.first()
    print(f"Testing first group: {first_group}")
    
    try:
        # Test serializer
        serializer = ManifestGroupSerializer(first_group)
        data = serializer.data
        
        print("✅ Serializer works!")
        
        # Check for key fields
        key_fields = ['family', 'family_mappings']
        for field in key_fields:
            if field in data:
                print(f"✅ '{field}' field is present")
                if data[field]:
                    print(f"   Value: {data[field]}")
                else:
                    print(f"   Value: None (no family assigned)")
            else:
                print(f"❌ '{field}' field is MISSING")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Serializer failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_serializer()
    print(f"\nTest result: {'SUCCESS' if success else 'FAILED'}")
