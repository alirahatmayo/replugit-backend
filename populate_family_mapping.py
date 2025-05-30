#!/usr/bin/env python3
"""
Data migration script to populate family_mapped_group for existing data
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from manifest.models import ManifestItem, ManifestGroup

def populate_family_mapping():
    """Populate family_mapped_group for all existing items"""
    
    print("🔄 Populating family_mapped_group for existing items...")
    
    # First, let's check what we're working with
    total_items = ManifestItem.objects.count()
    groups_with_families = ManifestGroup.objects.filter(product_family__isnull=False)
    print(f"📊 Total items: {total_items}")
    print(f"📊 Groups with families: {groups_with_families.count()}")
    
    # Check items in groups with families
    items_in_family_groups = ManifestItem.objects.filter(
        group__product_family__isnull=False
    )
    print(f"📊 Items in groups with families: {items_in_family_groups.count()}")
      # Update items one by one with debugging
    updated_count = 0
    for item in items_in_family_groups:  # Update all items, not just first 10
        if item.update_family_mapping_status():
            updated_count += 1
    
    print(f"✅ Updated {updated_count} items")
    
    # Show final statistics
    mapped_items = ManifestItem.objects.filter(family_mapped_group__isnull=False)
    print(f"📊 Items with family mapping: {mapped_items.count()}")
    
    return updated_count

if __name__ == "__main__":
    populate_family_mapping()
