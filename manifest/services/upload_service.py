import pandas as pd
import logging
from django.core.files.storage import default_storage
from django.contrib.auth.models import AnonymousUser
from ..models import Manifest, ManifestItem

logger = logging.getLogger(__name__)

class ManifestUploadService:
    """
    Service for handling manifest file uploads and initial processing
    """
    
    @staticmethod
    def process_upload(file_obj, name, user=None, reference=None, notes=None):
        """
        Process an uploaded manifest file
        
        Args:
            file_obj: The uploaded file object
            name: Name for the manifest
            user: User who uploaded the file (optional, can be None or AnonymousUser)
            reference: Optional reference identifier
            notes: Optional notes about the manifest
            
        Returns:
            Manifest: The created manifest object
            
        Raises:
            Exception: If there's an error processing the file
        """
        try:
            # Create manifest fields dictionary
            manifest_data = {
                'name': name,
                'status': 'pending',
                'file_type': file_obj.name.split('.')[-1].lower(),
                'reference': reference,
                'notes': notes
            }
            
            # Only set uploaded_by if user is a valid User instance
            if user and not isinstance(user, AnonymousUser):
                manifest_data['uploaded_by'] = user
            
            # Create a new manifest record
            manifest = Manifest.objects.create(**manifest_data)
            
            # Save the file
            file_path = default_storage.save(f'manifests/{manifest.id}/{file_obj.name}', file_obj)
            manifest.file = file_path  # Changed from file_path to file
            manifest.save()
            
            logger.info(f"Manifest file saved: {file_path}")
            return manifest
            
        except Exception as e:
            logger.error(f"Error uploading manifest: {str(e)}", exc_info=True)
            raise Exception(f"Failed to upload manifest: {str(e)}")