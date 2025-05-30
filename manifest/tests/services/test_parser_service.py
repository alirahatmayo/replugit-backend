from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from manifest.models import Manifest, ManifestItem
from manifest.services.parser_service import ManifestParserService
from manifest.services.upload_service import ManifestUploadService
import pandas as pd
import mock
import io

class ManifestParserServiceTestCase(TestCase):
    def setUp(self):
        # Create a test CSV file
        self.file_content = b'manufacturer,model,processor,memory,storage\nLenovo,X1 Carbon,Intel i7,16GB,512GB\nHP,EliteBook,Intel i5,8GB,256GB'
        self.test_file = SimpleUploadedFile(
            name='test_manifest.csv',
            content=self.file_content,
            content_type='text/csv'
        )
        
        # Create a manifest for testing
        self.manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Test Manifest'
        )

    def tearDown(self):
        # Clean up any files created during tests
        manifests = Manifest.objects.all()
        for manifest in manifests:
            if manifest.file and default_storage.exists(manifest.file.name):
                default_storage.delete(manifest.file.name)
    
    def test_parse_manifest_with_id(self):
        """Test parsing a manifest using its ID"""
        items_count = ManifestParserService.parse_manifest(manifest_id=self.manifest.id)
        
        # Check that the correct number of items were created (2 rows in the CSV)
        self.assertEqual(items_count, 2)
        
        # Check that manifest status was updated
        self.manifest.refresh_from_db()
        self.assertEqual(self.manifest.status, 'mapping')
        self.assertEqual(self.manifest.row_count, 2)
        
        # Verify the items were created correctly
        items = ManifestItem.objects.filter(manifest=self.manifest)
        self.assertEqual(items.count(), 2)
        
        # Check the content of the first item
        first_item = items.get(row_number=1)
        self.assertEqual(first_item.raw_data.get('manufacturer'), 'Lenovo')
        self.assertEqual(first_item.raw_data.get('model'), 'X1 Carbon')
        
        # Check the content of the second item
        second_item = items.get(row_number=2)
        self.assertEqual(second_item.raw_data.get('manufacturer'), 'HP')
        self.assertEqual(second_item.raw_data.get('model'), 'EliteBook')

    def test_parse_manifest_with_object(self):
        """Test parsing a manifest using the manifest object"""
        items_count = ManifestParserService.parse_manifest(manifest=self.manifest)
        
        # Check that the correct number of items were created
        self.assertEqual(items_count, 2)
        
        # Verify the items were created correctly
        items = ManifestItem.objects.filter(manifest=self.manifest)
        self.assertEqual(items.count(), 2)

    def test_parse_manifest_no_parameters(self):
        """Test that an exception is raised when no parameters are provided"""
        with self.assertRaises(Exception) as context:
            ManifestParserService.parse_manifest()
            
        self.assertIn("Either manifest or manifest_id must be provided", str(context.exception))

    @mock.patch('manifest.services.parser_service.default_storage.open')
    def test_parse_manifest_with_excel(self, mock_open):
        """Test parsing an Excel file"""
        # Create a mock Excel file
        excel_data = pd.DataFrame({
            'manufacturer': ['Dell', 'Asus'],
            'model': ['Latitude', 'ZenBook'],
            'processor': ['Intel i7', 'AMD Ryzen'],
            'memory': ['16GB', '8GB'],
            'storage': ['512GB', '1TB']
        })
        excel_buffer = io.BytesIO()
        excel_data.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        # Set up the mock to return our Excel buffer
        mock_open.return_value.__enter__.return_value = excel_buffer
        
        # Update the manifest to have an Excel file type
        self.manifest.file_type = 'xlsx'
        self.manifest.save()
        
        # Parse the manifest
        items_count = ManifestParserService.parse_manifest(manifest=self.manifest)
        
        # Check that items were created (2 rows in the Excel file)
        self.assertEqual(items_count, 2)
        
    @mock.patch('manifest.services.parser_service.default_storage.open')
    def test_parse_manifest_exception_handling(self, mock_open):
        """Test error handling during parsing"""
        # Setup the mock to raise an exception
        mock_open.side_effect = Exception("File error")
        
        # Attempt to parse and verify it raises an exception
        with self.assertRaises(Exception) as context:
            ManifestParserService.parse_manifest(manifest=self.manifest)
            
        self.assertIn("Failed to parse manifest", str(context.exception))
        
        # Check that the manifest status was updated to 'failed'
        self.manifest.refresh_from_db()
        self.assertEqual(self.manifest.status, 'failed')
        
    def test_get_suggested_mappings(self):
        """Test getting suggested column mappings"""
        # First parse the manifest to create items
        ManifestParserService.parse_manifest(manifest=self.manifest)
        
        # Get suggested mappings
        mappings = ManifestParserService.get_suggested_mappings(self.manifest)
        
        # Verify the mappings
        self.assertIn('manufacturer', mappings.values())
        self.assertIn('model', mappings.values())
        self.assertIn('processor', mappings.values())
        self.assertIn('memory', mappings.values())
        self.assertIn('storage', mappings.values())
        
    def test_get_suggested_mappings_no_items(self):
        """Test suggested mappings when there are no items"""
        # Don't parse the manifest, so there are no items
        mappings = ManifestParserService.get_suggested_mappings(self.manifest)
        
        # Should return an empty dictionary
        self.assertEqual(mappings, {})
