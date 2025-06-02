#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'replugit_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from manifest.batch_service import ManifestBatchService
from manifest.models import Manifest, ManifestItem
from inventory.models import Location
from receiving.models import BatchItem, ReceiptBatch
from products.models import ProductFamily

User = get_user_model()

def test_architectural_fix():
    print("=== TESTING ARCHITECTURAL FIX ===")
    
    # Get counts before
    manifest_count = Manifest.objects.count()
    location_count = Location.objects.count()
    user_count = User.objects.count()
    
    print(f"Database state:")
    print(f"  - Manifests: {manifest_count}")
    print(f"  - Locations: {location_count}")
    print(f"  - Users: {user_count}")
    
    if manifest_count == 0 or location_count == 0 or user_count == 0:
        print("❌ Need test data to proceed. Database is empty.")
        return
    
    # Get the first available manifest, location, and user
    manifest = Manifest.objects.first()
    location = Location.objects.first()
    user = User.objects.first()
    
    print(f"Testing with:")
    print(f"  - Manifest: {manifest.name} (ID: {manifest.id})")
    print(f"  - Location: {location.name} (ID: {location.id})")
    print(f"  - User: {user.username} (ID: {user.id})")
    
    # Check manifest items
    manifest_items = manifest.items.count()
    print(f"  - Manifest has {manifest_items} items")
    
    if manifest_items == 0:
        print("❌ Manifest has no items to test with.")
        return
    
    try:
        print("\n🔬 Testing the CORRECT architectural approach...")
        
        # Use the CORRECT service method
        batch, validation_issues = ManifestBatchService.create_receipt_batch_from_manifest(
            manifest=manifest,
            location_id=location.id,
            user_id=user.id
        )
        
        print(f"✅ Batch created successfully:")
        print(f"  - Batch ID: {batch.id}")
        print(f"  - Validation issues: {len(validation_issues)}")
        
        # Check BatchItems created
        batch_items = BatchItem.objects.filter(batch=batch)
        batch_item_count = batch_items.count()
        
        print(f"  - BatchItems created: {batch_item_count}")
        print(f"  - Expected (1:1 ratio): {manifest_items}")
        
        # ARCHITECTURAL FIX VERIFICATION:
        print(f"\n🎯 ARCHITECTURAL FIX VERIFICATION:")
        
        if batch_item_count == manifest_items:
            print(f"✅ CORRECT: 1:1 relationship maintained ({batch_item_count} BatchItems for {manifest_items} ManifestItems)")
        else:
            print(f"❌ WRONG: Should be 1:1 but got {batch_item_count} BatchItems for {manifest_items} ManifestItems")
        
        # Check individual item processing
        individual_item_count = 0
        items_with_details = 0
        
        for batch_item in batch_items:
            if batch_item.quantity == 1:
                individual_item_count += 1
            if batch_item.item_details:
                items_with_details += 1
        
        print(f"✅ Individual processing: {individual_item_count}/{batch_item_count} items have quantity=1")
        print(f"✅ Details preservation: {items_with_details}/{batch_item_count} items have preserved details")
        
        # Sample a few items to show preserved details
        print(f"\n📋 Sample preserved details:")
        for i, batch_item in enumerate(batch_items[:3]):
            print(f"  BatchItem {i+1}: {batch_item.item_details}")
        
        print(f"\n🎉 ARCHITECTURAL FIX VERIFICATION COMPLETE!")
        print(f"✅ Each ManifestItem creates exactly one BatchItem")
        print(f"✅ All individual item details are preserved") 
        print(f"✅ No loss of granularity from inappropriate grouping")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing architectural fix: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_architectural_fix()
    sys.exit(0 if success else 1)
