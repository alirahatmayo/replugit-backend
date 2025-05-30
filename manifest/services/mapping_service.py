import logging
from django.db import transaction
from django.utils import timezone
from ..models import Manifest, ManifestItem, ManifestTemplate, ManifestColumnMapping
from ..constants import SYSTEM_FIELDS

logger = logging.getLogger(__name__)

class ManifestMappingService:
    """
    Service for handling manifest column mappings
    """
    
    @staticmethod
    def apply_mapping(manifest_id=None, manifest=None, column_mappings=None, save_as_template=False, template_name=None):
        """
        Apply column mappings to a manifest
        
        Args:
            manifest_id: The ID of the manifest to map (alternative to manifest)
            manifest: The Manifest object (alternative to manifest_id)
            column_mappings: Dictionary of source_column -> target_field mappings
            save_as_template: Whether to save the mapping as a template
            template_name: Name for the template (if save_as_template is True)
            
        Returns:
            dict: Result with success status and data
            
        Raises:
            Exception: If there's an error mapping the columns
        """
        try:
            with transaction.atomic():
                # Get manifest either from object or ID
                if manifest is None and manifest_id is None:
                    raise Exception("Either manifest or manifest_id must be provided")
                
                if manifest is None:
                    manifest = Manifest.objects.get(id=manifest_id)
                
                # Validate column_mappings
                if not column_mappings or not isinstance(column_mappings, dict):
                    raise Exception("Column mappings must be provided as a dictionary")
                
                logger.info(f"Applying column mappings to manifest {manifest.id}: {column_mappings}")
                
                # Validate the mappings against system fields
                validation_result = ManifestMappingService.validate_mappings(
                    manifest=manifest,
                    column_mappings=column_mappings
                )
                
                if not validation_result['valid']:
                    logger.warning(f"Invalid column mappings: {validation_result['errors']}")
                    # We only warn but don't stop the process, as some use cases may need flexibility
                
                # Save as template if requested
                template = None
                if save_as_template and template_name:
                    # Check if a template with this name already exists
                    existing = ManifestTemplate.objects.filter(name=template_name).first()
                    if existing:
                        logger.info(f"Template with name '{template_name}' already exists, updating it")
                        template = existing
                        # Clear existing mappings
                        template.column_mappings.all().delete()
                    else:
                        template = ManifestTemplate.objects.create(
                            name=template_name,
                            created_by=manifest.uploaded_by if hasattr(manifest, 'uploaded_by') and manifest.uploaded_by else None,
                            default_values={}  # Can be expanded later
                        )
                    
                    # Create column mappings for the template with enhanced metadata
                    template_mappings = []
                    source_headers = []
                    
                    # Get system field definitions for enhanced metadata
                    system_fields_dict = {field['value']: field for field in SYSTEM_FIELDS}
                    
                    for idx, (source, target) in enumerate(column_mappings.items()):
                        if target and target != 'not_mapped':  # Only save non-empty, non-"not_mapped" mappings
                            # Get additional metadata from system fields
                            field_info = system_fields_dict.get(target, {})
                            group_key = field_info.get('group', 'general')
                            is_required = field_info.get('is_required', False)
                            
                            template_mappings.append(
                                ManifestColumnMapping(
                                    template=template,
                                    source_column=source,
                                    target_field=target,
                                    group_key=group_key,
                                    is_required=is_required,
                                    processing_order=idx
                                )
                            )
                            source_headers.append(source)
                    
                    if template_mappings:
                        ManifestColumnMapping.objects.bulk_create(template_mappings)
                    
                    # Store original headers in template metadata
                    if not template.metadata:
                        template.metadata = {}
                    template.metadata['headers'] = source_headers
                    template.save()
                    
                    # Link template to manifest
                    manifest.template = template
                
                # Store mappings in manifest metadata
                if not manifest.metadata:
                    manifest.metadata = {}
                manifest.metadata['column_mappings'] = column_mappings
                
                # Update manifest status to validation
                manifest.status = 'validation'
                manifest.save()
                
                # Apply mappings to all manifest items
                items = ManifestItem.objects.filter(manifest=manifest)
                mapped_count = 0
                error_count = 0
                
                for item in items:
                    try:
                        item_updated = False
                        raw_data = item.raw_data or {}
                        
                        # Initialize or update mapped_data
                        if not item.mapped_data:
                            item.mapped_data = {}
                        
                        # Apply each mapping to the item
                        for source_col, target_field in column_mappings.items():
                            if not target_field or target_field == 'not_mapped':  # Skip empty or "not_mapped" mappings
                                continue
                                
                            # Check if this column exists in raw data
                            if source_col in raw_data:
                                # Get the value from raw data
                                value = raw_data.get(source_col)
                                
                                # Store the mapped value in mapped_data
                                item.mapped_data[target_field] = value
                                
                                # Also set the field value on the item model if it exists
                                if hasattr(item, target_field):
                                    setattr(item, target_field, value)
                                    
                                item_updated = True
                        
                        if item_updated:
                            item.status = 'mapped'
                            item.processed_at = timezone.now()
                            item.save()
                            mapped_count += 1
                    except Exception as e:
                        logger.error(f"Error mapping item {item.id}: {str(e)}", exc_info=True)
                        item.status = 'error'
                        item.error_message = f"Mapping error: {str(e)}"
                        item.save()
                        error_count += 1
                
                # Update manifest counts
                manifest.processed_count = mapped_count
                manifest.error_count = error_count
                manifest.save(update_fields=['processed_count', 'error_count'])
                
                logger.info(f"Applied mappings to {mapped_count} manifest items (errors: {error_count})")
                
                return {
                    'success': True,
                    'manifest_id': manifest.id,
                    'template_id': template.id if template else None,
                    'mapped_count': mapped_count,
                    'error_count': error_count,
                    'validation_warnings': validation_result.get('errors', []) if not validation_result.get('valid', True) else []
                }
                
        except Exception as e:
            logger.error(f"Error applying column mappings: {str(e)}", exc_info=True)
            raise Exception(f"Failed to apply column mappings: {str(e)}")
    
    @staticmethod
    def get_template_mappings(template_id):
        """
        Get mappings from a saved template
        
        Args:
            template_id: The ID of the template
            
        Returns:
            dict: Dictionary of source_column -> target_field mappings
        """
        try:
            template = ManifestTemplate.objects.get(id=template_id)
            mappings = {}
            
            for mapping in template.column_mappings.all():
                mappings[mapping.source_column] = mapping.target_field
                
            return mappings
            
        except ManifestTemplate.DoesNotExist:
            logger.error(f"Template with ID {template_id} not found")
            return {}
        except Exception as e:
            logger.error(f"Error getting template mappings: {str(e)}", exc_info=True)
            return {}
    
    @staticmethod
    def validate_mappings(manifest, column_mappings):
        """
        Validate column mappings against system fields requirements and data types
        
        Args:
            manifest: The Manifest object
            column_mappings: Dictionary of source_column -> target_field mappings
            
        Returns:
            dict: Validation result with valid status and errors list
        """
        errors = []
        
        # Get sample data from manifest to check data types
        sample_item = ManifestItem.objects.filter(manifest=manifest).first()
        if not sample_item or not sample_item.raw_data:
            return {'valid': True, 'errors': []}  # No data to validate against
        
        raw_data = sample_item.raw_data
        
        # Create a lookup of field requirements based on SYSTEM_FIELDS
        system_field_lookup = {field['value']: field for field in SYSTEM_FIELDS}
        
        # Check for required fields that are not mapped
        required_fields = [field['value'] for field in SYSTEM_FIELDS if field.get('is_required', False)]
        mapped_targets = set(column_mappings.values())
        missing_required = [field for field in required_fields if field not in mapped_targets]
        
        if missing_required:
            for field in missing_required:
                field_label = system_field_lookup.get(field, {}).get('label', field)
                errors.append(f"Required field '{field_label}' is not mapped")
        
        # Check for data type compatibility
        for source_col, target_field in column_mappings.items():
            if target_field == 'not_mapped' or not target_field:
                continue
                
            field_info = system_field_lookup.get(target_field, {})
            expected_data_type = field_info.get('data_type')
            
            if not expected_data_type or expected_data_type == 'any':
                continue  # Skip validation for fields with no specified type
                
            # Get a sample value from raw data
            if source_col in raw_data:
                sample_value = raw_data[source_col]
                
                # Basic type checking
                if expected_data_type == 'decimal' or expected_data_type == 'number':
                    try:
                        # Try to convert to float
                        if sample_value and not isinstance(sample_value, (int, float)):
                            float(str(sample_value).replace(',', ''))
                    except (ValueError, TypeError):
                        field_label = field_info.get('label', target_field)
                        errors.append(
                            f"Column '{source_col}' may not contain valid numeric data for field '{field_label}'"
                        )
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }