import pandas as pd
import logging
from django.core.files.storage import default_storage
from ..models import Manifest, ManifestItem

logger = logging.getLogger(__name__)

class ManifestParserService:
    """
    Service for parsing manifest files and creating manifest items
    """
    
    @staticmethod
    def parse_manifest(manifest_id=None, manifest=None):
        """
        Parse a manifest file and create manifest items
        
        Args:
            manifest_id: The ID of the manifest to parse (alternative to manifest)
            manifest: The manifest object to parse (alternative to manifest_id)
            
        Returns:
            int: Number of items created
            
        Raises:
            Exception: If there's an error parsing the file
        """
        try:
            # Get manifest either from object or ID
            if manifest is None and manifest_id is None:
                raise Exception("Either manifest or manifest_id must be provided")
                
            if manifest is None:
                manifest = Manifest.objects.get(id=manifest_id)
                
            # Get the correct file path - use name attribute for FileField objects
            file_path = manifest.file.name if hasattr(manifest.file, 'name') else manifest.file
            
            with default_storage.open(file_path, 'rb') as file:
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
            
            # Determine if the file has a header
            has_header = True  # Assume it has headers by default
            manifest.has_header = has_header
            manifest.row_count = len(df)
            manifest.save()
            
            # Create manifest items from rows
            items_to_create = []
            for i, row in df.iterrows():
                # Convert row to dict and handle NaN values
                row_data = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                
                items_to_create.append(ManifestItem(
                    manifest=manifest,
                    row_number=i + 1,
                    raw_data=row_data,
                    status='pending'
                ))
            
            # Bulk create to improve performance
            if items_to_create:
                ManifestItem.objects.bulk_create(items_to_create, batch_size=1000)
                logger.info(f"Created {len(items_to_create)} manifest items for manifest ID: {manifest.id}")
            
            # Update manifest status to 'mapping' to trigger the mapping dialog in the frontend
            manifest.status = 'mapping'
            manifest.save()
            
            return len(items_to_create)
        
        except Exception as e:
            logger.error(f"Error parsing manifest file: {str(e)}", exc_info=True)
            
            # Make sure we have a manifest object before trying to update its status
            if isinstance(manifest, Manifest):
                manifest.status = 'failed'
                manifest.save()
                
            raise Exception(f"Failed to parse manifest: {str(e)}")
            
    @staticmethod
    def get_suggested_mappings(manifest):
        """
        Suggest column mappings based on column names
        
        Args:
            manifest: The manifest object to analyze
            
        Returns:
            dict: Dictionary of suggested mappings
        """
        # Get a sample item
        sample_item = ManifestItem.objects.filter(manifest=manifest).first()
        if not sample_item:
            return {}
        
        raw_data = sample_item.raw_data or {}
        
        # Simple mapping based on column name similarity
        common_fields = [
            'manufacturer', 'model', 'processor', 'memory', 'storage', 'condition',
            'serial', 'serial_number', 'sku', 'product_id', 'price', 'quantity'
        ]
        
        suggested_mappings = {}
        for col in raw_data.keys():
            col_lower = col.lower().replace(' ', '_')
            
            # Look for exact matches
            if col_lower in common_fields:
                suggested_mappings[col] = col_lower
                continue
            
            # Look for partial matches
            for field in common_fields:
                if field in col_lower:
                    suggested_mappings[col] = field
                    break
        
        return suggested_mappings