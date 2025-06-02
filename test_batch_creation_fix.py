#!/usr/bin/env python
"""
Test script to verify that BatchItems are correctly created from individual ManifestItems
instead of grouped ManifestGroups, preserving unit-level granularity.
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import transaction
from django.contrib.auth.models import User
from manifest.models import Manifest, ManifestItem
from receiving.models import ReceiptBatch, BatchItem
from inventory.models import Location
from products.models import ProductFamily
from manifest.batch_service import ManifestBatchService


def test_batch_creation_from_manifest_items():
    """Test that BatchItems are created from individual ManifestItems, not groups"""
    
    print("🔧 Testing Batch Creation Fix...")
    print("=" * 50)
    
    with transaction.atomic():
        # Create test data
        try:
            # Get or create a location
            location, _ = Location.objects.get_or_create(
                name="Test Location",
                defaults={"address": "123 Test St"}
            )
            
            # Get or create a product family
            family, _ = ProductFamily.objects.get_or_create(
                name="Test Laptop Family",
                defaults={"family_type": "laptop", "sku": "TEST-LAPTOP"}
            )
            
            # Create a test manifest
            manifest = Manifest.objects.create(
                name="Test Manifest for Batch Creation",
                status="validated",
                manifest_number="TEST-001"
            )
            
            # Create individual ManifestItems with different serial numbers and specs
            items_data = [
                {
                    'manufacturer': 'Lenovo',
                    'model': 'ThinkPad T14',
                    'processor': 'Intel i5-1135G7',
                    'memory': '16GB',
                    'storage': '512GB SSD',
                    'serial': 'LN001234',
                    'condition_grade': 'A',
                    'quantity': 1,
                    'unit_cost': 850.00
                },
                {
                    'manufacturer': 'Lenovo', 
                    'model': 'ThinkPad T14',
                    'processor': 'Intel i5-1135G7',
                    'memory': '16GB',
                    'storage': '512GB SSD', 
                    'serial': 'LN001235',  # Different serial
                    'condition_grade': 'B',  # Different condition
                    'quantity': 1,
                    'unit_cost': 750.00  # Different price
                },
                {
                    'manufacturer': 'Lenovo',
                    'model': 'ThinkPad T14', 
                    'processor': 'Intel i7-1165G7',  # Different processor
                    'memory': '32GB',  # Different memory
                    'storage': '1TB SSD',  # Different storage
                    'serial': 'LN001236',  # Different serial
                    'condition_grade': 'A',
                    'quantity': 1,
                    'unit_cost': 1200.00
                }
            ]
            
            # Create ManifestItems
            manifest_items = []
            for i, item_data in enumerate(items_data, 1):
                manifest_item = ManifestItem.objects.create(
                    manifest=manifest,
                    row_number=i,
                    raw_data=item_data,
                    mapped_data=item_data,
                    status='validated',
                    product_family=family,
                    **item_data
                )
                manifest_items.append(manifest_item)
            
            print(f"✅ Created {len(manifest_items)} ManifestItems with different specs:")
            for item in manifest_items:
                print(f"   - {item.serial}: {item.processor}, {item.memory}, {item.storage}, Grade {item.condition_grade}")
            
            # Test the CORRECT batch service
            print(f"\n🔄 Creating batch using CORRECT service (individual items)...")
            batch, validation_issues = ManifestBatchService.create_receipt_batch_from_manifest(
                manifest=manifest,
                location_id=location.id,
                user_id=None
            )
            
            # Verify results
            batch_items = BatchItem.objects.filter(batch=batch)
            print(f"\n📊 Results:")
            print(f"   - ManifestItems created: {len(manifest_items)}")
            print(f"   - BatchItems created: {batch_items.count()}")
            print(f"   - Validation issues: {len(validation_issues)}")
            
            if validation_issues:
                print(f"   - Issues: {validation_issues}")
            
            # The key test: We should have ONE BatchItem per ManifestItem
            expected_batch_items = len(manifest_items)
            actual_batch_items = batch_items.count()
            
            print(f"\n🎯 Core Test - Unit-Level Granularity:")
            print(f"   - Expected BatchItems (1 per ManifestItem): {expected_batch_items}")
            print(f"   - Actual BatchItems created: {actual_batch_items}")
            
            if actual_batch_items == expected_batch_items:
                print(f"   ✅ PASS: Correct 1:1 relationship maintained!")
            else:
                print(f"   ❌ FAIL: Expected {expected_batch_items}, got {actual_batch_items}")
                return False
            
            # Test unit-level details preservation
            print(f"\n🔍 Testing Unit-Level Details Preservation:")
            for i, batch_item in enumerate(batch_items):
                item_details = batch_item.item_details or {}
                original_item = manifest_items[i]
                
                print(f"   BatchItem {i+1}:")
                print(f"     - Serial: {item_details.get('serial', 'MISSING')} (expected: {original_item.serial})")
                print(f"     - Processor: {item_details.get('processor', 'MISSING')} (expected: {original_item.processor})")
                print(f"     - Memory: {item_details.get('memory', 'MISSING')} (expected: {original_item.memory})")
                print(f"     - Condition: {item_details.get('condition_grade', 'MISSING')} (expected: {original_item.condition_grade})")
                
                # Verify critical details are preserved
                if (item_details.get('serial') == original_item.serial and
                    item_details.get('processor') == original_item.processor and
                    item_details.get('memory') == original_item.memory and
                    item_details.get('condition_grade') == original_item.condition_grade):
                    print(f"     ✅ Unit details correctly preserved")
                else:
                    print(f"     ❌ Unit details NOT preserved correctly")
                    return False
            
            print(f"\n🎉 SUCCESS: Batch creation fix is working correctly!")
            print(f"   - Each ManifestItem creates exactly one BatchItem")
            print(f"   - All unit-level details (serial, specs, condition) are preserved")
            print(f"   - No loss of granularity from grouping")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during test: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = test_batch_creation_from_manifest_items()
    if success:
        print(f"\n✅ All tests passed! The architectural fix is working correctly.")
    else:
        print(f"\n❌ Tests failed! There may still be issues with the implementation.")
    
    sys.exit(0 if success else 1)
