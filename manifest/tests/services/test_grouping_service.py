from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from manifest.models import Manifest, ManifestItem, ManifestGroup
from manifest.services.grouping_service import ManifestGroupingService
from manifest.services.upload_service import ManifestUploadService
from manifest.services.parser_service import ManifestParserService
from manifest.services.mapping_service import ManifestMappingService
import mock

class ManifestGroupingServiceTestCase(TestCase):
    def setUp(self):
        # Create a test CSV file with multiple items that can be grouped
        self.file_content = b"""manufacturer,model,processor,memory,storage,serial,price
Lenovo,X1 Carbon,Intel i7,16GB,512GB,ABC123,1200
Lenovo,X1 Carbon,Intel i7,16GB,512GB,DEF456,1200
HP,EliteBook,Intel i5,8GB,256GB,XYZ789,950
HP,EliteBook,Intel i5,8GB,256GB,UVW321,950
Dell,Latitude,Intel i7,16GB,512GB,QRS987,1100
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
            'price': 'unit_price'
        }
        
        # Apply mappings
        ManifestMappingService.apply_mapping(
            manifest=self.manifest,
            column_mappings=self.column_mappings
        )

    def tearDown(self):
        # Clean up any files created during tests
        manifests = Manifest.objects.all()
        for manifest in manifests:
            if manifest.file and default_storage.exists(manifest.file.name):
                default_storage.delete(manifest.file.name)
    
    def test_group_items_default_fields(self):
        """Test grouping items with default fields"""
        # Group the items
        result = ManifestGroupingService.group_items(manifest_id=self.manifest.id)
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        self.assertIn('group_count', result['data'])
        self.assertIn('item_count', result['data'])
        
        # Check that the correct number of groups were created
        # We should have 3 groups: Lenovo X1 Carbon, HP EliteBook, Dell Latitude
        self.assertEqual(result['data']['group_count'], 3)
        self.assertEqual(result['data']['item_count'], 5)  # Total items processed
        
        # Check groups in the database
        groups = ManifestGroup.objects.filter(manifest=self.manifest)
        self.assertEqual(groups.count(), 3)
        
        # Check that items were assigned to groups
        items = ManifestItem.objects.filter(manifest=self.manifest)
        for item in items:
            self.assertIsNotNone(item.group)
            
        # Check specific groups
        lenovo_group = groups.get(manufacturer='Lenovo', model='X1 Carbon')
        self.assertEqual(lenovo_group.quantity, 2)
        
        hp_group = groups.get(manufacturer='HP', model='EliteBook')
        self.assertEqual(hp_group.quantity, 2)
        
        dell_group = groups.get(manufacturer='Dell', model='Latitude')
        self.assertEqual(dell_group.quantity, 1)
        
    def test_group_items_custom_fields(self):
        """Test grouping items with custom fields"""
        # Group only by manufacturer (should result in 3 groups)
        result = ManifestGroupingService.group_items(
            manifest_id=self.manifest.id,
            group_fields=['manufacturer']
        )
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        
        # Check that the correct number of groups were created
        self.assertEqual(result['data']['group_count'], 3)
        
        # Check groups in the database
        groups = ManifestGroup.objects.filter(manifest=self.manifest)
        self.assertEqual(groups.count(), 3)
        
        # Group by manufacturer and processor (should still be 3 groups in this case)
        ManifestGroup.objects.all().delete()
        ManifestItem.objects.filter(manifest=self.manifest).update(group=None)
        
        result = ManifestGroupingService.group_items(
            manifest_id=self.manifest.id,
            group_fields=['manufacturer', 'processor']
        )
        
        # Check groups
        groups = ManifestGroup.objects.filter(manifest=self.manifest)
        self.assertEqual(groups.count(), 3)
        
    def test_group_items_nonexistent_manifest(self):
        """Test handling of nonexistent manifest"""
        result = ManifestGroupingService.group_items(manifest_id=99999)
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('Manifest with ID 99999 not found', result['error'])
        
    def test_group_items_empty_manifest(self):
        """Test grouping when manifest has no items"""
        # Create a new manifest but don't parse it (so it has no items)
        new_manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Empty Manifest'
        )
        
        result = ManifestGroupingService.group_items(manifest_id=new_manifest.id)
        
        # Should succeed but with 0 groups
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['group_count'], 0)
        self.assertEqual(result['data']['item_count'], 0)
        
    def test_regroup_items(self):
        """Test regrouping items after initial grouping"""
        # First group with default fields
        ManifestGroupingService.group_items(manifest_id=self.manifest.id)
        
        # Verify initial groups
        initial_groups = ManifestGroup.objects.filter(manifest=self.manifest)
        self.assertEqual(initial_groups.count(), 3)
        
        # Now regroup with just manufacturer
        result = ManifestGroupingService.group_items(
            manifest_id=self.manifest.id,
            group_fields=['manufacturer']
        )
        
        # Verify new grouping
        new_groups = ManifestGroup.objects.filter(manifest=self.manifest)
        self.assertEqual(new_groups.count(), 3)  # Still 3 manufacturers
        
        # But the groups should be different
        lenovo_group = new_groups.get(manufacturer='Lenovo')
        self.assertEqual(lenovo_group.quantity, 2)
        
    @mock.patch('manifest.services.grouping_service.ManifestItem.objects.filter')
    def test_exception_handling(self, mock_filter):
        """Test exception handling"""
        # Make the filter raise an exception
        mock_filter.side_effect = Exception("Test exception")
        
        result = ManifestGroupingService.group_items(manifest_id=self.manifest.id)
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('Test exception', result['error'])
