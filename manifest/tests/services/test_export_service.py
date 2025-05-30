from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.http import HttpResponse
from manifest.models import Manifest, ManifestItem, ManifestGroup
from manifest.services.export_service import ManifestExportService
from manifest.services.upload_service import ManifestUploadService
from manifest.services.parser_service import ManifestParserService
from manifest.services.mapping_service import ManifestMappingService
import pandas as pd
import io
import mock

class ManifestExportServiceTestCase(TestCase):
    def setUp(self):
        # Create a test CSV file
        self.file_content = b"""manufacturer,model,processor,memory,storage,serial,condition
Lenovo,X1 Carbon,Intel i7,16GB,512GB,ABC123,A
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

    def tearDown(self):
        # Clean up any files created during tests
        manifests = Manifest.objects.all()
        for manifest in manifests:
            if manifest.file and default_storage.exists(manifest.file.name):
                default_storage.delete(manifest.file.name)
    
    def test_export_remapped_manifest_xlsx(self):
        """Test exporting manifest data to Excel format"""
        items = ManifestItem.objects.filter(manifest=self.manifest)
        
        # Export to Excel
        response = ManifestExportService.export_remapped_manifest(
            manifest=self.manifest,
            items=items,
            format='xlsx'
        )
        
        # Verify the response is an HTTP response with Excel content type
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue('attachment; filename=' in response['Content-Disposition'])
        
        # Try to read the Excel file to verify content
        xlsx_data = response.content
        df = pd.read_excel(io.BytesIO(xlsx_data), sheet_name='Data')
        
        # Check that the DataFrame has the expected columns and rows
        self.assertEqual(len(df), 2)  # 2 rows
        self.assertIn('Manufacturer', df.columns)
        self.assertIn('Model', df.columns)
        self.assertIn('Serial Number', df.columns)
        
        # Check specific values
        self.assertEqual(df['Manufacturer'].iloc[0], 'Lenovo')
        self.assertEqual(df['Model'].iloc[0], 'X1 Carbon')
        self.assertEqual(df['Serial Number'].iloc[0], 'ABC123')
        
    def test_export_remapped_manifest_csv(self):
        """Test exporting manifest data to CSV format"""
        items = ManifestItem.objects.filter(manifest=self.manifest)
        
        # Export to CSV
        response = ManifestExportService.export_remapped_manifest(
            manifest=self.manifest,
            items=items,
            format='csv'
        )
        
        # Verify the response is an HTTP response with CSV content type
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertTrue('attachment; filename=' in response['Content-Disposition'])
        
        # Try to read the CSV file to verify content
        csv_data = response.content
        df = pd.read_csv(io.BytesIO(csv_data))
        
        # Check that the DataFrame has the expected columns and rows
        self.assertEqual(len(df), 2)  # 2 rows
        self.assertIn('Manufacturer', df.columns)
        self.assertIn('Model', df.columns)
        self.assertIn('Serial Number', df.columns)
        
        # Check specific values
        self.assertEqual(df['Manufacturer'].iloc[0], 'Lenovo')
        self.assertEqual(df['Model'].iloc[0], 'X1 Carbon')
        self.assertEqual(df['Serial Number'].iloc[0], 'ABC123')
        
    @mock.patch('manifest.services.export_service.pd.DataFrame')
    def test_export_error_handling(self, mock_dataframe):
        """Test error handling during export"""
        items = ManifestItem.objects.filter(manifest=self.manifest)
        
        # Setup the mock to raise an exception
        mock_dataframe.side_effect = Exception("DataFrame creation error")
        
        # Attempt to export and verify it raises an exception
        with self.assertRaises(Exception):
            ManifestExportService.export_remapped_manifest(
                manifest=self.manifest,
                items=items,
                format='xlsx'
            )
