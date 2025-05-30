#!/usr/bin/env python3
"""
Simple test to verify basic family mapping functionality
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from manifest.models import ManifestItem, ManifestGroup, Manifest
from products.models import ProductFamily

def main():
    print("🚀 Simple Family Mapping Test")
    print("=" * 40)
    
    # Check if we have data
    manifests = Manifest.objects.all()
    items = ManifestItem.objects.all()
    groups = ManifestGroup.objects.all()
    families = ProductFamily.objects.all()
    
    print(f"📊 Data Overview:")
    print(f"   - Manifests: {manifests.count()}")
    print(f"   - Manifest Items: {items.count()}")
    print(f"   - Manifest Groups: {groups.count()}")
    print(f"   - Product Families: {families.count()}")
    
    if items.exists():
        # Test first item
        item = items.first()
        print(f"\n🔍 Testing first item (ID: {item.id}):")
        print(f"   - group: {item.group}")
        print(f"   - family_mapped_group: {item.family_mapped_group}")
        print(f"   - status: {item.status}")
        print(f"   - effective_status: {item.effective_status}")
        print(f"   - is_mapped_to_family: {item.is_mapped_to_family}")
        print(f"   - mapped_family: {item.mapped_family}")
        
        # Test serializer
        from manifest.serializers import ManifestItemSerializer
        serializer = ManifestItemSerializer(item)
        data = serializer.data
        print(f"\n📡 Serializer output:")
        print(f"   - status: {data.get('status')}")
        print(f"   - is_family_mapped: {data.get('is_family_mapped')}")
        print(f"   - mapped_family: {data.get('mapped_family')}")
    
    if groups.exists():
        # Check groups with families
        groups_with_families = groups.filter(product_family__isnull=False)
        print(f"\n👥 Groups with families: {groups_with_families.count()}")
        
        if groups_with_families.exists():
            group = groups_with_families.first()
            print(f"   - Group {group.id}: {group.manufacturer} {group.model}")
            print(f"   - Family: {group.product_family.name if group.product_family else 'None'}")
            print(f"   - Items in group: {group.items.count()}")
            print(f"   - Family mapped items: {group.family_mapped_items.count()}")
    
    print("\n✅ Basic test completed successfully!")
    
if __name__ == "__main__":
    main()
