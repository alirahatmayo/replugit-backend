from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from manifest.models import Manifest, ManifestItem, ManifestTemplate, ManifestColumnMapping
from manifest.services.mapping_service import ManifestMappingService
from manifest.services.upload_service import ManifestUploadService
from manifest.services.parser_service import ManifestParserService
from manifest.constants import SYSTEM_FIELDS
import mock

class ManifestMappingServiceTestCase(TestCase):
    def setUp(self):
        # Create a test CSV file with varied column names
        self.file_content = b'manufacturer,model,cpu,memory,storage,serial_number,price\nLenovo,X1 Carbon,Intel i7,16GB,512GB,ABC123,1200\nHP,EliteBook,Intel i5,8GB,256GB,XYZ789,950'
        self.test_file = SimpleUploadedFile(
            name='test_manifest.csv',
            content=self.file_content,
            content_type='text/csv'
        )
        
        # Create and parse a manifest for testing
        self.manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Test Manifest'
        )
        ManifestParserService.parse_manifest(manifest=self.manifest)
        
        # Define column mappings for testing
        self.column_mappings = {
            'manufacturer': 'manufacturer',
            'model': 'model',
            'cpu': 'processor',
            'memory': 'memory',
            'storage': 'storage',
            'serial_number': 'serial',
            'price': 'unit_price'
        }

    def tearDown(self):
        # Clean up any files created during tests
        manifests = Manifest.objects.all()
        for manifest in manifests:
            if manifest.file and default_storage.exists(manifest.file.name):
                default_storage.delete(manifest.file.name)
    
    def test_apply_mapping(self):
        """Test applying column mappings to a manifest"""
        result = ManifestMappingService.apply_mapping(
            manifest=self.manifest,
            column_mappings=self.column_mappings
        )
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        self.assertIn('processed_count', result['data'])
        self.assertEqual(result['data']['processed_count'], 2)  # We have 2 rows in our test file
        
        # Check that the manifest status was updated
        self.manifest.refresh_from_db()
        self.assertEqual(self.manifest.status, 'validation')
        
        # Check that the items were updated with mapped_data
        items = ManifestItem.objects.filter(manifest=self.manifest)
        for item in items:
            self.assertIsNotNone(item.mapped_data)
            self.assertEqual(item.status, 'mapped')
            
            # Check specific mappings
            self.assertEqual(item.manufacturer, item.raw_data['manufacturer'])
            self.assertEqual(item.model, item.raw_data['model'])
            self.assertEqual(item.processor, item.raw_data['cpu'])
            self.assertEqual(item.memory, item.raw_data['memory'])
            self.assertEqual(item.storage, item.raw_data['storage'])
            self.assertEqual(item.serial, item.raw_data['serial_number'])
            self.assertEqual(float(item.unit_price), float(item.raw_data['price']))
            
    def test_apply_mapping_with_id(self):
        """Test applying column mappings using manifest ID"""
        result = ManifestMappingService.apply_mapping(
            manifest_id=self.manifest.id,
            column_mappings=self.column_mappings
        )
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        
    def test_apply_mapping_save_as_template(self):
        """Test saving mappings as a template"""
        result = ManifestMappingService.apply_mapping(
            manifest=self.manifest,
            column_mappings=self.column_mappings,
            save_as_template=True,
            template_name="Test Template"
        )
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        
        # Check that a template was created
        template = ManifestTemplate.objects.filter(name="Test Template").first()
        self.assertIsNotNone(template)
        
        # Check that template mappings were created
        mappings = ManifestColumnMapping.objects.filter(template=template)
        self.assertEqual(mappings.count(), len(self.column_mappings))
        
        # Check that specific mappings were created correctly
        for source, target in self.column_mappings.items():
            mapping = mappings.filter(source_column=source, target_field=target).first()
            self.assertIsNotNone(mapping)
            
    def test_apply_mapping_no_parameters(self):
        """Test that an exception is handled when no parameters are provided"""
        result = ManifestMappingService.apply_mapping()
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('Either manifest or manifest_id must be provided', result['error'])
        
    def test_apply_mapping_invalid_mappings(self):
        """Test handling of invalid column mappings"""
        # Test with None
        result = ManifestMappingService.apply_mapping(manifest=self.manifest, column_mappings=None)
        self.assertFalse(result['success'])
        
        # Test with non-dict
        result = ManifestMappingService.apply_mapping(manifest=self.manifest, column_mappings="not a dict")
        self.assertFalse(result['success'])
        
    def test_apply_mapping_missing_required_fields(self):
        """Test handling of missing required fields in mappings"""
        # Create mappings without required serial field
        incomplete_mappings = {
            'manufacturer': 'manufacturer',
            'model': 'model',
            # serial is missing
        }
        
        result = ManifestMappingService.apply_mapping(
            manifest=self.manifest,
            column_mappings=incomplete_mappings
        )
        
        # Result should still be successful, but with warnings
        self.assertTrue(result['success'])
        self.assertIn('warnings', result['data'])
        self.assertTrue(any('serial' in warning for warning in result['data']['warnings']))
        
    def test_apply_template_to_manifest(self):
        """Test applying a template to a manifest"""
        # First create a template
        ManifestMappingService.apply_mapping(
            manifest=self.manifest,
            column_mappings=self.column_mappings,
            save_as_template=True,
            template_name="Test Template"
        )
        
        template = ManifestTemplate.objects.get(name="Test Template")
        
        # Create a new manifest with the same structure
        new_file = SimpleUploadedFile(
            name='new_manifest.csv',
            content=self.file_content,
            content_type='text/csv'
        )
        
        new_manifest = ManifestUploadService.process_upload(
            file_obj=new_file,
            name='New Manifest'
        )
        ManifestParserService.parse_manifest(manifest=new_manifest)
        
        # Apply the template to the new manifest
        result = ManifestMappingService.apply_template_to_manifest(
            manifest=new_manifest,
            template_id=template.id
        )
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        
        # Check that the items were properly mapped
        items = ManifestItem.objects.filter(manifest=new_manifest)
        for item in items:
            self.assertEqual(item.status, 'mapped')
            self.assertIsNotNone(item.mapped_data)
