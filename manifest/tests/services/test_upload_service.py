from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from manifest.models import Manifest
from manifest.services.upload_service import ManifestUploadService
import os
import mock

User = get_user_model()

class ManifestUploadServiceTestCase(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create a mock file for testing
        self.file_content = b'manufacturer,model,processor,memory,storage\nLenovo,X1 Carbon,Intel i7,16GB,512GB'
        self.test_file = SimpleUploadedFile(
            name='test_manifest.csv',
            content=self.file_content,
            content_type='text/csv'
        )

    def tearDown(self):
        # Clean up any files created during tests
        manifests = Manifest.objects.all()
        for manifest in manifests:
            if manifest.file and default_storage.exists(manifest.file.name):
                default_storage.delete(manifest.file.name)
    
    def test_process_upload_with_user(self):
        """Test manifest upload with a valid user"""
        manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Test Manifest',
            user=self.user,
            reference='PO-12345',
            notes='Test notes'
        )
        
        # Check the manifest was created correctly
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.name, 'Test Manifest')
        self.assertEqual(manifest.status, 'pending')
        self.assertEqual(manifest.file_type, 'csv')
        self.assertEqual(manifest.reference, 'PO-12345')
        self.assertEqual(manifest.notes, 'Test notes')
        self.assertEqual(manifest.uploaded_by, self.user)
        
        # Check that the file was saved
        self.assertTrue(manifest.file)
        self.assertTrue(default_storage.exists(manifest.file.name))
        
    def test_process_upload_without_user(self):
        """Test manifest upload without a user"""
        manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Anonymous Manifest',
            user=None
        )
        
        # Check the manifest was created correctly
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.name, 'Anonymous Manifest')
        self.assertIsNone(manifest.uploaded_by)
        
    def test_process_upload_with_anonymous_user(self):
        """Test manifest upload with an AnonymousUser"""
        from django.contrib.auth.models import AnonymousUser
        
        manifest = ManifestUploadService.process_upload(
            file_obj=self.test_file,
            name='Anonymous User Manifest',
            user=AnonymousUser()
        )
        
        # Check the manifest was created correctly
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.name, 'Anonymous User Manifest')
        self.assertIsNone(manifest.uploaded_by)
        
    @mock.patch('manifest.services.upload_service.default_storage.save')
    def test_upload_error_handling(self, mock_save):
        """Test error handling during file upload"""
        # Setup the mock to raise an exception
        mock_save.side_effect = Exception("Storage error")
        
        # Attempt to upload and verify it raises an exception
        with self.assertRaises(Exception) as context:
            ManifestUploadService.process_upload(
                file_obj=self.test_file,
                name='Error Manifest'
            )
            
        self.assertIn("Failed to upload manifest", str(context.exception))
