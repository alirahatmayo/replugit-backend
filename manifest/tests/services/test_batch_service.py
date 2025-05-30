from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.contrib.auth import get_user_model
from manifest.models import Manifest, ManifestItem, ManifestGroup
from manifest.services.batch_service import ManifestBatchService
from manifest.services.upload_service import ManifestUploadService
from manifest.services.parser_service import ManifestParserService
from manifest.services.mapping_service import ManifestMappingService
from manifest.services.grouping_service import ManifestGroupingService
from receiving.models import ReceiptBatch, BatchItem
from products.models import ProductFamily
from inventory.models import Location
import mock

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
        )
        
        # Create test product families
        self.product_family1 = ProductFamily.objects.create(
            name='Laptops',
            description='All laptops'
        )
        
        self.product_family2 = ProductFamily.objects.create(
            name='Desktop Computers',
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
        
        # Group items
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
        """Test creating a receiving batch from a manifest"""
        result = ManifestBatchService.create_batch_from_manifest(
            manifest_id=self.manifest.id,
            location_id=self.location.id,
            user=self.user
        )
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        self.assertIn('batch_id', result)
        
        # Check that a batch was created
        batch = ReceiptBatch.objects.get(id=result['batch_id'])
        self.assertIsNotNone(batch)
        self.assertEqual(batch.created_by, self.user)
        self.assertEqual(batch.location, self.location)
        
        # Check that the batch is associated with the manifest
        self.manifest.refresh_from_db()
        self.assertEqual(self.manifest.receipt_batch, batch)
        
        # Check that batch items were created from manifest groups
        batch_items = BatchItem.objects.filter(batch=batch)
        self.assertEqual(batch_items.count(), 2)  # We should have 2 groups
        
        # Check that batch items have product families assigned
        lenovo_item = batch_items.filter(manufacturer='Lenovo').first()
        self.assertEqual(lenovo_item.product_family, self.product_family1)
        self.assertEqual(lenovo_item.quantity, 2)  # 2 Lenovo laptops
        
        hp_item = batch_items.filter(manufacturer='HP').first()
        self.assertEqual(hp_item.product_family, self.product_family2)
        self.assertEqual(hp_item.quantity, 1)  # 1 HP laptop
        
    def test_create_batch_nonexistent_manifest(self):
        """Test error handling with nonexistent manifest"""
        with self.assertRaises(ValueError) as context:
            ManifestBatchService.create_batch_from_manifest(
                manifest_id=99999,
                location_id=self.location.id,
                user=self.user
            )
            
        self.assertIn('Manifest with ID 99999 not found', str(context.exception))
        
    def test_create_batch_nonexistent_location(self):
        """Test error handling with nonexistent location"""
        with self.assertRaises(ValueError) as context:
            ManifestBatchService.create_batch_from_manifest(
                manifest_id=self.manifest.id,
                location_id=99999,
                user=self.user
            )
            
        self.assertIn('Location with ID 99999 not found', str(context.exception))
        
    def test_create_batch_no_groups(self):
        """Test error handling with a manifest that has no groups"""
        # Create a new manifest without grouping
        new_manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Empty Groups Manifest'
        )
        ManifestParserService.parse_manifest(manifest=new_manifest)
        ManifestMappingService.apply_mapping(
            manifest=new_manifest,
            column_mappings=self.column_mappings
        )
        
        # Try to create a batch
        with self.assertRaises(ValueError) as context:
            ManifestBatchService.create_batch_from_manifest(
                manifest_id=new_manifest.id,
                location_id=self.location.id,
                user=self.user
            )
            
        self.assertIn('No grouped items found', str(context.exception))
        
    @mock.patch('manifest.services.batch_service.transaction.atomic')
    def test_error_handling_during_batch_creation(self, mock_atomic):
        """Test error handling during batch creation transaction"""
        # Setup the mock to raise an exception during the transaction
        mock_atomic.side_effect = Exception("Transaction error")
        
        # The service method should catch and handle this exception
        result = ManifestBatchService.create_batch_from_manifest(
            manifest_id=self.manifest.id,
            location_id=self.location.id,
            user=self.user
        )
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('Transaction error', result['error'])
