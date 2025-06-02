#!/usr/bin/env python
"""
Quick test to verify the unique constraint has been removed
"""
import os
import sys

print("Starting constraint fix test...")

try:
    import django
    print("Django imported successfully")
    
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'replugit.settings')
    django.setup()
    print("Django setup complete")

    from django.test import TestCase
    from django.db import transaction
    from manifest.models import Manifest, ManifestItem, ManifestGroup
    from receiving.models import ReceiptBatch, BatchItem
    from products.models import ProductFamily
    from inventory.models import Location
    from django.contrib.auth.models import User
    import uuid
    
    print("All imports successful")

except Exception as e:
    print(f"Setup error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def test_multiple_same_family_items():
    """Test that we can create multiple BatchItems with the same product family"""
    print("Testing multiple BatchItems with same product family...")
    
    try:
        with transaction.atomic():
            # Create test data
            user = User.objects.create_user(username=f'testuser_{uuid.uuid4().hex[:8]}', password='testpass')
            location = Location.objects.create(name=f'Test Location {uuid.uuid4().hex[:8]}', code=f'TEST{uuid.uuid4().hex[:4].upper()}')
            product_family = ProductFamily.objects.create(
                name=f'Test Laptops {uuid.uuid4().hex[:8]}',
                sku=f'TEST-{uuid.uuid4().hex[:8]}',
                description='Test product family'
            )
            
            print(f"Created test data: User={user.id}, Location={location.id}, ProductFamily={product_family.id}")
            
            # Create a batch
            batch = ReceiptBatch.objects.create(
                reference=f'TEST-BATCH-{uuid.uuid4().hex[:8]}',
                location=location,
                created_by=user
            )
            
            print(f"Created batch: {batch.id}")
            
            # Try to create multiple BatchItems with the same product family
            batch_item1 = BatchItem.objects.create(
                batch=batch,
                product_family=product_family,
                quantity=1,
                unit_cost=100.00
            )
            print(f"✅ Created first BatchItem: {batch_item1.id}")
            
            batch_item2 = BatchItem.objects.create(
                batch=batch,
                product_family=product_family,
                quantity=1,
                unit_cost=150.00
            )
            print(f"✅ Created second BatchItem: {batch_item2.id}")
            
            batch_item3 = BatchItem.objects.create(
                batch=batch,
                product_family=product_family,
                quantity=1,
                unit_cost=200.00
            )
            print(f"✅ Created third BatchItem: {batch_item3.id}")
            
            print(f"✅ SUCCESS: Created 3 BatchItems with same product family in one batch!")
            print(f"   Batch: {batch.id}")
            print(f"   Product Family: {product_family.name}")
            print(f"   BatchItems: {[item.id for item in BatchItem.objects.filter(batch=batch)]}")
            
            return True
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running main test...")
    success = test_multiple_same_family_items()
    if success:
        print("\n🎉 Constraint fix verified! Multiple BatchItems with same product family can be created.")
    else:
        print("\n💥 Constraint fix failed! Still cannot create multiple BatchItems with same product family.")
    
    sys.exit(0 if success else 1)
