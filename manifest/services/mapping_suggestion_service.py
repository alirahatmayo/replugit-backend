import logging
from ..models import Manifest, ManifestItem
from ..constants import SYSTEM_FIELDS

logger = logging.getLogger(__name__)

class ManifestMappingSuggestionService:
    """
    Service for suggesting column mappings for manifest files based on content analysis.
    """
    
    @staticmethod
    def suggest_mappings(manifest_id=None, manifest=None):
        """
        Analyze manifest data and suggest column mappings based on content patterns
        
        Args:
            manifest_id: The ID of the manifest to analyze (alternative to manifest)
            manifest: The Manifest object (alternative to manifest_id)
            
        Returns:
            dict: Result with success status and suggested mappings data
        """
        try:
            # Get manifest either from object or ID
            if manifest is None and manifest_id is None:
                raise Exception("Either manifest or manifest_id must be provided")
                
            # Handle case where a Manifest object is passed as manifest_id parameter
            from django.db.models import Model
            if manifest is None and isinstance(manifest_id, Model):
                manifest = manifest_id
                manifest_id = None
                
            # If we still need to get the manifest from the database
            if manifest is None:
                try:
                    # Ensure manifest_id is an integer
                    manifest_id = int(manifest_id)
                    from ..models import Manifest
                    manifest = Manifest.objects.get(id=manifest_id)
                except (ValueError, TypeError):
                    raise Exception(f"Invalid manifest ID: {manifest_id}")
            
            # Get a sample of items to analyze
            from ..models import ManifestItem
            sample_items = ManifestItem.objects.filter(manifest=manifest).order_by('id')[:10]
            if not sample_items:
                return {'success': False, 'error': 'No items found in manifest'}
            
            # Extract column names from the first item
            column_names = list(sample_items[0].raw_data.keys()) if sample_items[0].raw_data else []
            if not column_names:
                return {'success': False, 'error': 'No columns found in manifest data'}
            
            # Build field patterns from system field definitions
            field_patterns = {}
            
            # Create patterns dictionary from SYSTEM_FIELDS
            for field in SYSTEM_FIELDS:
                field_value = field['value']
                if field_value != 'not_mapped':
                    # Get patterns directly from field definition
                    patterns = field.get('patterns', [field_value])
                    field_patterns[field_value] = patterns
            
            # Build suggestion mapping
            suggestions = {}
            for column in column_names:
                column_lower = column.lower().replace(' ', '').replace('_', '').replace('-', '')
                
                for field, patterns in field_patterns.items():
                    # Check for exact matches
                    if column_lower in patterns:
                        suggestions[column] = field
                        break
                        
                    # Check for partial matches - column contains pattern
                    for pattern in patterns:
                        if pattern in column_lower:
                            suggestions[column] = field
                            break
                    
                    # If we already found a match, no need to check more patterns
                    if column in suggestions:
                        break
            
            # Additional check for more complex patterns
            for column in column_names:
                if column not in suggestions:
                    column_lower = column.lower()
                    
                    # Check for specific common patterns not caught above
                    if 'capacity' in column_lower or 'size' in column_lower:
                        if any(term in column_lower for term in ['ram', 'memory', 'mem']):
                            suggestions[column] = 'memory'
                        elif any(term in column_lower for term in ['disk', 'drive', 'storage', 'ssd', 'hdd']):
                            suggestions[column] = 'storage'
                            
                    # Check for price/cost related fields
                    elif any(term in column_lower for term in ['price', 'cost', '$', 'amount', 'sale', 'retail']):
                        suggestions[column] = 'price'
                        
            # Log the results
            logger.info(f"Generated {len(suggestions)} mapping suggestions for manifest {manifest.id}")
            logger.debug(f"Suggested mappings: {suggestions}")
            
            # Return with consistent response structure
            return {
                'success': True,
                'data': {
                    'suggestions': suggestions,
                    'all_columns': column_names
                }
            }
            
        except Manifest.DoesNotExist:
            return {'success': False, 'error': f'Manifest with ID {manifest_id} not found'}
        except Exception as e:
            logger.error(f"Error generating mapping suggestions: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Failed to generate suggested mappings: {str(e)}'}