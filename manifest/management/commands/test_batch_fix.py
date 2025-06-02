from django.core.management.base import BaseCommand
from django.db import transaction
from manifest.models import Manifest, ManifestItem
from receiving.models import ReceiptBatch, BatchItem
from inventory.models import Location
from products.models import ProductFamily
from manifest.batch_service import ManifestBatchService


class Command(BaseCommand):
    help = 'Test that the architectural fix is working: BatchItems created from individual ManifestItems'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Testing Batch Creation Architectural Fix")
        self.stdout.write("=" * 60)
        
        try:
            with transaction.atomic():
                # Get or create test location
                location, created = Location.objects.get_or_create(
                    name="Test Location", 
                    defaults={"address": "Test Address"}
                )
                if created:
                    self.stdout.write(f"✅ Created test location: {location.name}")
                else:
                    self.stdout.write(f"✅ Using existing location: {location.name}")
                
                # Get or create test product family
                family, created = ProductFamily.objects.get_or_create(
                    name="Test Laptop Family",
                    defaults={
                        "family_type": "laptop", 
                        "sku": "TEST-FAMILY",
                        "description": "Test family for verification"
                    }
                )
                if created:
                    self.stdout.write(f"✅ Created test product family: {family.name}")
                else:
                    self.stdout.write(f"✅ Using existing product family: {family.name}")
                
                # Create test manifest
                manifest = Manifest.objects.create(
                    name="Test Manifest - Individual Item Processing",
                    status="validated",
                    manifest_number="FIX-TEST-001"
                )
                self.stdout.write(f"✅ Created test manifest: {manifest.name}")
                
                # Create test ManifestItems with DIFFERENT specifications
                test_items = [
                    {
                        'row_number': 1,
                        'manufacturer': 'Lenovo',
                        'model': 'ThinkPad T14',
                        'serial': 'SN001-UNIQUE',
                        'processor': 'Intel i5-1135G7',
                        'memory': '16GB',
                        'storage': '512GB SSD',
                        'condition_grade': 'A',
                        'quantity': 1,
                        'unit_cost': 850.00
                    },
                    {
                        'row_number': 2,
                        'manufacturer': 'Lenovo',
                        'model': 'ThinkPad T14',
                        'serial': 'SN002-DIFFERENT',  # Different serial
                        'processor': 'Intel i7-1165G7',  # Different processor
                        'memory': '32GB',  # Different memory
                        'storage': '1TB SSD',  # Different storage
                        'condition_grade': 'B',  # Different condition
                        'quantity': 1,
                        'unit_cost': 1200.00  # Different price
                    },
                    {
                        'row_number': 3,
                        'manufacturer': 'HP',  # Different manufacturer
                        'model': 'EliteBook 850',  # Different model
                        'serial': 'SN003-ANOTHER',
                        'processor': 'Intel i5-1145G7',
                        'memory': '16GB',
                        'storage': '256GB SSD',
                        'condition_grade': 'C',  # Different condition
                        'quantity': 1,
                        'unit_cost': 600.00
                    }
                ]
                
                # Create ManifestItems
                manifest_items = []
                for item_data in test_items:
                    raw_data = item_data.copy()
                    manifest_item = ManifestItem.objects.create(
                        manifest=manifest,
                        raw_data=raw_data,
                        mapped_data=raw_data,
                        status='validated',
                        product_family=family,
                        **item_data
                    )
                    manifest_items.append(manifest_item)
                
                self.stdout.write(f"✅ Created {len(manifest_items)} ManifestItems with unique specifications:")
                for item in manifest_items:
                    self.stdout.write(f"   • {item.serial}: {item.manufacturer} {item.model}, {item.processor}, {item.memory}, Grade {item.condition_grade}")
                
                # TEST: Use the correct batch service
                self.stdout.write(f"\n🚀 Testing Correct Batch Service...")
                batch, validation_issues = ManifestBatchService.create_receipt_batch_from_manifest(
                    manifest=manifest,
                    location_id=location.id,
                    user_id=None
                )
                
                # Verify results
                batch_items = BatchItem.objects.filter(batch=batch)
                
                self.stdout.write(f"\n📊 RESULTS:")
                self.stdout.write(f"   • ManifestItems: {len(manifest_items)}")
                self.stdout.write(f"   • BatchItems created: {batch_items.count()}")
                self.stdout.write(f"   • Validation issues: {len(validation_issues)}")
                
                # CRITICAL TEST: 1:1 relationship
                success = True
                if batch_items.count() == len(manifest_items):
                    self.stdout.write(self.style.SUCCESS(f"   ✅ CORRECT: 1:1 relationship maintained (each ManifestItem → 1 BatchItem)"))
                else:
                    self.stdout.write(self.style.ERROR(f"   ❌ WRONG: Expected {len(manifest_items)} BatchItems, got {batch_items.count()}"))
                    success = False
                
                # TEST: Unit-level details preserved
                self.stdout.write(f"\n🔍 UNIT-LEVEL DETAILS PRESERVATION:")
                for i, batch_item in enumerate(batch_items):
                    original_item = manifest_items[i]
                    details = batch_item.item_details or {}
                    
                    serial_match = details.get('serial') == original_item.serial
                    processor_match = details.get('processor') == original_item.processor
                    memory_match = details.get('memory') == original_item.memory
                    condition_match = details.get('condition_grade') == original_item.condition_grade
                    
                    if serial_match and processor_match and memory_match and condition_match:
                        self.stdout.write(self.style.SUCCESS(f"   ✅ BatchItem {i+1}: All details preserved"))
                        self.stdout.write(f"      Serial: {details.get('serial')} | Processor: {details.get('processor')}")
                        self.stdout.write(f"      Memory: {details.get('memory')} | Condition: {details.get('condition_grade')}")
                    else:
                        self.stdout.write(self.style.ERROR(f"   ❌ BatchItem {i+1}: Details NOT preserved correctly"))
                        self.stdout.write(f"      Expected: {original_item.serial}, {original_item.processor}, {original_item.memory}, {original_item.condition_grade}")
                        self.stdout.write(f"      Got: {details.get('serial')}, {details.get('processor')}, {details.get('memory')}, {details.get('condition_grade')}")
                        success = False
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f"\n🎉 SUCCESS! Architectural fix is working correctly:"))
                    self.stdout.write(self.style.SUCCESS(f"   ✅ Each ManifestItem creates exactly one BatchItem"))
                    self.stdout.write(self.style.SUCCESS(f"   ✅ All unit-level details (serial, specs, condition) preserved"))
                    self.stdout.write(self.style.SUCCESS(f"   ✅ No loss of granularity from inappropriate grouping"))
                    self.stdout.write(self.style.SUCCESS(f"   ✅ Ready for unit management with serial numbers"))
                else:
                    self.stdout.write(self.style.ERROR(f"\n❌ FAILURE! There are still issues with the implementation"))
                
                # Clean up test data
                manifest.delete()
                self.stdout.write(f"\n🧹 Cleaned up test data")
                
                return success
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Test failed with error: {e}"))
            import traceback
            traceback.print_exc()
            return False
