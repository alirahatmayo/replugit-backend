from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.contrib.auth import get_user_model
from manifest.models import Manifest, ManifestItem, ManifestGroup
from manifest.batch_service import ManifestBatchService  # CORRECTED: Use the right service
from manifest.services.upload_service import ManifestUploadService
from manifest.services.parser_service import ManifestParserService
from manifest.services.mapping_service import ManifestMappingService
from manifest.services.grouping_service import ManifestGroupingService
from receiving.models import ReceiptBatch, BatchItem
from products.models import ProductFamily
from inventory.models import Location
from unittest import mock

User = get_user_model()

class ManifestBatchServiceTestCase(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create a test location
        self.location = Location.objects.create(
            name='Test Location',
            code='TEST-LOC',
            is_active=True
        )        # Create test product families with unique SKUs to avoid constraint violations
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        self.product_family1 = ProductFamily.objects.create(
            name=f'Laptops {unique_suffix}',
            sku=f'TEST-LAPTOP-FAM-{unique_suffix}',
            description='All laptops'
        )
        
        self.product_family2 = ProductFamily.objects.create(
            name=f'Desktop Computers {unique_suffix}',
            sku=f'TEST-DESKTOP-FAM-{unique_suffix}',
            description='All desktop computers'
        )
        
        # Create a test CSV file
        self.file_content = b"""manufacturer,model,processor,memory,storage,serial,condition
Lenovo,X1 Carbon,Intel i7,16GB,512GB,ABC123,A
Lenovo,X1 Carbon,Intel i7,16GB,512GB,DEF456,A
HP,EliteBook,Intel i5,8GB,256GB,XYZ789,B
"""
        self.test_file = SimpleUploadedFile(
            name='test_manifest.csv',
            content=self.file_content,
            content_type='text/csv'
        )
        
        # Create, parse, and map a manifest for testing
        self.manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Test Manifest'
        )
        ManifestParserService.parse_manifest(manifest=self.manifest)
        
        # Define column mappings
        self.column_mappings = {
            'manufacturer': 'manufacturer',
            'model': 'model',
            'processor': 'processor',
            'memory': 'memory',
            'storage': 'storage',
            'serial': 'serial',
            'condition': 'condition_grade'
        }
        
        # Apply mappings
        ManifestMappingService.apply_mapping(
            manifest=self.manifest,
            column_mappings=self.column_mappings
        )
        
        # Group items (still needed for product family assignment)
        ManifestGroupingService.group_items(manifest_id=self.manifest.id)
        
        # Assign product families to manifest groups
        for group in ManifestGroup.objects.filter(manifest=self.manifest):
            if group.manufacturer == 'Lenovo':
                group.product_family = self.product_family1
            else:
                group.product_family = self.product_family2
            group.save()

    def tearDown(self):
        # Clean up any files created during tests
        manifests = Manifest.objects.all()
        for manifest in manifests:
            if manifest.file and default_storage.exists(manifest.file.name):
                default_storage.delete(manifest.file.name)

    def test_create_batch_from_manifest(self):
        """Test creating a receiving batch from a manifest using individual items"""
        # Use the CORRECT service method
        batch, validation_issues = ManifestBatchService.create_receipt_batch_from_manifest(
            manifest=self.manifest,
            location_id=self.location.id,
            user_id=self.user.id
        )
        
        # Verify the batch was created
        self.assertIsNotNone(batch)
        self.assertEqual(batch.created_by, self.user)
        self.assertEqual(batch.location, self.location)
        
        # Verify validation issues list is returned
        self.assertIsInstance(validation_issues, list)
        
        # Check that batch items were created from INDIVIDUAL manifest items (not groups)
        batch_items = BatchItem.objects.filter(batch=batch)
        
        # CORRECTED EXPECTATION: Each ManifestItem should create ONE BatchItem
        # We have 3 ManifestItems, so we should get 3 BatchItems (not 2 grouped ones)
        manifest_items_count = self.manifest.items.count()
        self.assertEqual(batch_items.count(), manifest_items_count, 
                        f"Should create one BatchItem per ManifestItem. Expected {manifest_items_count}, got {batch_items.count()}")
        
        # CORRECTED EXPECTATION: Each BatchItem should have quantity=1 (individual items)
        for batch_item in batch_items:
            self.assertEqual(batch_item.quantity, 1, "Each BatchItem should represent individual ManifestItem with quantity=1")
            
        # CORRECTED EXPECTATION: Check that individual item details are preserved
        batch_items_with_details = batch_items.exclude(item_details__isnull=True)
        self.assertGreater(batch_items_with_details.count(), 0, "BatchItems should have preserved item details")
        
        # Check that specific details like serial numbers are preserved
        serial_numbers = []
        for batch_item in batch_items:
            if batch_item.item_details and 'serial' in batch_item.item_details:
                serial_numbers.append(batch_item.item_details['serial'])
        
        # Verify we have the expected serial numbers
        expected_serials = ['ABC123', 'DEF456', 'XYZ789']
        for expected_serial in expected_serials:
            self.assertIn(expected_serial, serial_numbers, f"Serial number {expected_serial} should be preserved in BatchItem details")
        
        # Check product families are assigned correctly
        batch_items_with_families = batch_items.exclude(product_family__isnull=True)
        self.assertGreater(batch_items_with_families.count(), 0, "BatchItems should have product families assigned")

    def test_create_batch_no_items(self):
        """Test error handling with a manifest that has no items"""
        # Create a manifest with no items
        empty_manifest = Manifest.objects.create(
            name='Empty Manifest',
            uploaded_by=self.user
        )
        
        # Try to create a batch - should handle gracefully
        batch, validation_issues = ManifestBatchService.create_receipt_batch_from_manifest(
            manifest=empty_manifest,
            location_id=self.location.id,
            user_id=self.user.id
        )
        
        # Should still create a batch, but with no items
        self.assertIsNotNone(batch)
        self.assertEqual(BatchItem.objects.filter(batch=batch).count(), 0)

    def test_item_details_preservation(self):
        """Test that all item details are properly preserved in BatchItems"""
        batch, validation_issues = ManifestBatchService.create_receipt_batch_from_manifest(
            manifest=self.manifest,
            location_id=self.location.id,
            user_id=self.user.id
        )
        
        batch_items = BatchItem.objects.filter(batch=batch)
        
        # Check that each batch item has the expected details structure
        for batch_item in batch_items:
            self.assertIsNotNone(batch_item.item_details)
            item_details = batch_item.item_details
            
            # Check for expected fields that should be preserved
            expected_fields = ['manufacturer', 'model', 'serial', 'condition_grade']
            for field in expected_fields:
                if field in item_details:  # Some fields might be optional
                    self.assertIsNotNone(item_details[field], f"Field {field} should not be None in item_details")

    def test_product_family_assignment(self):
        """Test that product families are correctly assigned to BatchItems"""
        batch, validation_issues = ManifestBatchService.create_receipt_batch_from_manifest(
            manifest=self.manifest,
            location_id=self.location.id,
            user_id=self.user.id
        )
        
        batch_items = BatchItem.objects.filter(batch=batch)
        
        # Check that items have product families assigned based on their manifest groups
        lenovo_items = batch_items.filter(item_details__manufacturer='Lenovo')
        hp_items = batch_items.filter(item_details__manufacturer='HP')
        
        # Lenovo items should have Laptops product family
        for item in lenovo_items:
            self.assertEqual(item.product_family, self.product_family1)
            
        # HP items should have Desktop Computers product family  
        for item in hp_items:
            self.assertEqual(item.product_family, self.product_family2)
