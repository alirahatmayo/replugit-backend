from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from manifest.models import Manifest, ManifestItem
from manifest.services.mapping_suggestion_service import ManifestMappingSuggestionService
from manifest.services.upload_service import ManifestUploadService
from manifest.services.parser_service import ManifestParserService
from manifest.constants import SYSTEM_FIELDS
import mock

class ManifestMappingSuggestionServiceTestCase(TestCase):
    def setUp(self):
        # Create a test CSV file with varied column names
        self.file_content = b'manufacturer,product_model,cpu type,memory_size_gb,storage capacity,serialNum,price $\nLenovo,X1 Carbon,Intel i7,16GB,512GB,ABC123,1200\nHP,EliteBook,Intel i5,8GB,256GB,XYZ789,950'
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

    def tearDown(self):
        # Clean up any files created during tests
        manifests = Manifest.objects.all()
        for manifest in manifests:
            if manifest.file and default_storage.exists(manifest.file.name):
                default_storage.delete(manifest.file.name)
    
    def test_suggest_mappings_with_manifest(self):
        """Test suggesting mappings using the manifest object"""
        result = ManifestMappingSuggestionService.suggest_mappings(manifest=self.manifest)
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertIn('suggestions', result['data'])
        self.assertIn('all_columns', result['data'])
        
        # Check that suggested mappings make sense
        suggestions = result['data']['suggestions']
        self.assertEqual(suggestions.get('manufacturer'), 'manufacturer')
        self.assertEqual(suggestions.get('product_model'), 'model')
        self.assertEqual(suggestions.get('cpu type'), 'processor')
        self.assertEqual(suggestions.get('memory_size_gb'), 'memory')
        self.assertEqual(suggestions.get('storage capacity'), 'storage')
        self.assertEqual(suggestions.get('serialNum'), 'serial')
        self.assertEqual(suggestions.get('price $'), 'price')
        
        # Check all columns are included
        all_columns = result['data']['all_columns']
        self.assertEqual(len(all_columns), 7)  # We have 7 columns in our test file
        
    def test_suggest_mappings_with_manifest_id(self):
        """Test suggesting mappings using the manifest ID"""
        result = ManifestMappingSuggestionService.suggest_mappings(manifest_id=self.manifest.id)
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        self.assertIn('suggestions', result['data'])
        
    def test_suggest_mappings_with_manifest_object_as_id(self):
        """Test suggesting mappings when manifest object is passed as manifest_id"""
        result = ManifestMappingSuggestionService.suggest_mappings(manifest_id=self.manifest)
        
        # Verify the result is successful
        self.assertTrue(result['success'])
        self.assertIn('suggestions', result['data'])
        
    def test_suggest_mappings_no_parameters(self):
        """Test that an exception is handled when no parameters are provided"""
        result = ManifestMappingSuggestionService.suggest_mappings()
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('Either manifest or manifest_id must be provided', result['error'])
        
    def test_suggest_mappings_invalid_id(self):
        """Test handling of invalid manifest ID"""
        result = ManifestMappingSuggestionService.suggest_mappings(manifest_id='invalid')
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('Invalid manifest ID', result['error'])
        
    def test_suggest_mappings_nonexistent_id(self):
        """Test handling of non-existent manifest ID"""
        result = ManifestMappingSuggestionService.suggest_mappings(manifest_id=99999)
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('not found', result['error'])
        
    def test_suggest_mappings_no_items(self):
        """Test suggesting mappings when manifest has no items"""
        # Create a new manifest but don't parse it (so it has no items)
        new_manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Empty Manifest'
        )
        
        result = ManifestMappingSuggestionService.suggest_mappings(manifest=new_manifest)
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('No items found in manifest', result['error'])
        
    @mock.patch('manifest.services.mapping_suggestion_service.ManifestItem.objects.filter')
    def test_suggest_mappings_with_empty_raw_data(self, mock_filter):
        """Test suggesting mappings when items have no raw data"""
        # Create a mock item with empty raw data
        mock_item = mock.Mock()
        mock_item.raw_data = {}
        mock_filter.return_value.order_by.return_value.__getitem__.return_value = [mock_item]
        
        result = ManifestMappingSuggestionService.suggest_mappings(manifest=self.manifest)
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('No columns found in manifest data', result['error'])
        
    @mock.patch.object(ManifestMappingSuggestionService, 'suggest_mappings')
    def test_exception_handling(self, mock_suggest):
        """Test general exception handling"""
        mock_suggest.side_effect = Exception("Test exception")
        
        result = ManifestMappingSuggestionService.suggest_mappings(manifest=self.manifest)
        
        # Verify the result indicates failure
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('Test exception', result['error'])
