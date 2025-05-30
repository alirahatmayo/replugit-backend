import logging
import uuid
import hashlib
from collections import defaultdict
from django.db import transaction
from ..models import Manifest, ManifestItem, ManifestGroup

logger = logging.getLogger(__name__)

class ManifestGroupingService:
    """
    Service for handling manifest item grouping
    """
    
    @staticmethod
    def _generate_group_statistics(items):
        """
        Generate statistical information about a group of manifest items
        
        Args:
            items: QuerySet of ManifestItem objects in the group
            
        Returns:
            dict: Statistical information about the group
        """
        stats = {}
        
        # Get row numbers if available
        row_numbers = []
        for item in items:
            if hasattr(item, 'row_number') and item.row_number:
                row_numbers.append(item.row_number)
            elif hasattr(item, 'mapped_data') and item.mapped_data and 'row_number' in item.mapped_data:
                row_numbers.append(item.mapped_data.get('row_number'))
        if row_numbers:
            stats['row_numbers'] = row_numbers
        
        # Count unique memory configurations
        memory_counts = {}
        for item in items:
            memory = getattr(item, 'memory', None)
            if memory:
                memory_counts[memory] = memory_counts.get(memory, 0) + 1
        if memory_counts:
            stats['memory_variations'] = memory_counts
        
        # Count unique storage configurations
        storage_counts = {}
        for item in items:
            storage = getattr(item, 'storage', None)
            if storage:
                storage_counts[storage] = storage_counts.get(storage, 0) + 1
        if storage_counts:
            stats['storage_variations'] = storage_counts
        
        # Count condition grades
        condition_counts = {}
        for item in items:
            condition = getattr(item, 'condition_grade', None)
            if condition:
                condition_counts[condition] = condition_counts.get(condition, 0) + 1
        if condition_counts:
            stats['condition_distribution'] = condition_counts
            
        return stats
    
    @staticmethod
    def group_items(manifest_id, group_fields=None):
        """
        Group manifest items based on specified fields
        
        Args:
            manifest_id: The ID of the manifest to group
            group_fields: List of fields to group by (default: manufacturer, model, processor)
            
        Returns:
            dict: Result with success status and data
            
        Raises:
            Exception: If there's an error grouping the items
        """
        try:
            if not group_fields:
                # Default to manufacturer, model and processor only
                group_fields = ["manufacturer", "model", "processor"]
                
            manifest = Manifest.objects.get(id=manifest_id)
            
            # Clear existing groups
            with transaction.atomic():
                # Delete existing groups for this manifest
                ManifestGroup.objects.filter(manifest=manifest).delete()
                
                # Reset group assignments for manifest items
                ManifestItem.objects.filter(manifest=manifest).update(group=None)
                
                # Get all items for this manifest
                items = ManifestItem.objects.filter(manifest=manifest)
                if not items.exists():
                    return {
                        "success": True,
                        "data": {
                            "group_count": 0,
                            "item_count": 0
                        }
                    }
                
                # Group items based on specified fields
                groups = defaultdict(list)
                for item in items:
                    if not hasattr(item, 'processed_data') or not item.processed_data:
                        # Fall back to the mapped_data if processed_data is not available
                        data_source = item.mapped_data if item.mapped_data else {}
                    else:
                        data_source = item.processed_data
                    
                    # Create a key based on the group fields
                    key_parts = []
                    for field in group_fields:
                        # Try to get value from mapped_data first, then fallback to direct attribute
                        value = data_source.get(field, "")
                        if not value and hasattr(item, field):
                            value = getattr(item, field) or ""
                        key_parts.append(str(value).lower())
                    
                    key = "|".join(key_parts)
                    # Create hash for the group_key field
                    hash_key = hashlib.md5(key.encode()).hexdigest()
                    groups[hash_key].append(item.id)
                  # Create groups and assign items
                group_objects = []
                
                for hash_key, item_ids in groups.items():
                    if not item_ids:
                        continue
                          # Get a sample item to extract group info
                    sample_item = ManifestItem.objects.get(id=item_ids[0])
                    
                    # Get all items in the group for statistics
                    group_items = ManifestItem.objects.filter(id__in=item_ids)
                    
                    # Generate statistics about the group
                    stats = ManifestGroupingService._generate_group_statistics(group_items)                # Extract manufacturer and model for direct fields
                    manufacturer = getattr(sample_item, 'manufacturer', None)
                    model = getattr(sample_item, 'model', None)
                    
                    # Create metadata with all relevant attributes
                    metadata = {
                        'processor': getattr(sample_item, 'processor', None),
                        'memory': getattr(sample_item, 'memory', None),
                        'storage': getattr(sample_item, 'storage', None),
                        'condition_grade': getattr(sample_item, 'condition_grade', None),
                        'group_fields': group_fields,
                        'grouped_at': str(uuid.uuid4()),  # Add a unique identifier for the grouping operation
                        'stats': stats  # Add statistical information about the group
                    }
                    group = ManifestGroup(
                        manifest=manifest,
                        group_key=hash_key,
                        quantity=len(item_ids),
                        manufacturer=manufacturer,
                        model=model,
                        metadata=metadata
                    )
                    group_objects.append(group)
                
                # Bulk create groups
                created_groups = ManifestGroup.objects.bulk_create(group_objects)                # Map items to their groups
                for i, (hash_key, item_ids) in enumerate(groups.items()):
                    if not item_ids:
                        continue
                    
                    group = created_groups[i]
                    ManifestItem.objects.filter(id__in=item_ids).update(group=group)
                    
                    # Generate a proper group key with the enhanced method
                    group.group_key = group.generate_group_key()
                    group.save(update_fields=['group_key'])
                
                return {
                    "success": True,
                    "data": {
                        "group_count": len(created_groups),
                        "item_count": sum(len(items) for items in groups.values())
                    }
                }
                
        except Exception as e:
            logger.error(f"Error grouping manifest items: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to group manifest items: {str(e)}"            }
            
    @staticmethod
    def get_groups(manifest_id):
        """
        Get all groups for a manifest
        
        Args:
            manifest_id: The ID of the manifest
            
        Returns:
            dict: Result with success status and data
            
        Raises:
            Exception: If there's an error fetching the groups
        """
        try:
            manifest = Manifest.objects.get(id=manifest_id)
            groups = ManifestGroup.objects.filter(manifest=manifest)
            result = []
            for group in groups:
                group_data = {
                    "id": group.id,
                    "manufacturer": group.manufacturer or group.get_metadata('manufacturer'),
                    "model": group.model or group.get_metadata('model'),
                    "processor": group.get_metadata('processor'),
                    "memory": group.get_metadata('memory'),
                    "storage": group.get_metadata('storage'),
                    "condition_grade": group.get_metadata('condition_grade'),
                    "quantity": group.quantity,
                    "unit_price": group.get_metadata('unit_price'),
                    "metadata": group.metadata,
                    "stats": group.get_metadata('stats')
                }
                result.append(group_data)
                
            return {
                "success": True,
                "data": result
            }
            
        except Manifest.DoesNotExist:
            return {
                "success": False,
                "error": f"Manifest with ID {manifest_id} not found"
            }        
        except Exception as e:
            logger.error(f"Error fetching manifest groups: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to fetch manifest groups: {str(e)}"
            }
            
    @staticmethod
    def _generate_group_statistics(items):
        """
        Generate statistical information about a group of manifest items
        
        Args:
            items: QuerySet of ManifestItem objects in the group
            
        Returns:
            dict: Statistical information about the group
        """
        stats = {}
        
        # Get row numbers if available
        row_numbers = []
        for item in items:
            if hasattr(item, 'row_number') and item.row_number:
                row_numbers.append(item.row_number)
            elif item.mapped_data and 'row_number' in item.mapped_data:
                row_numbers.append(item.mapped_data.get('row_number'))
        if row_numbers:
            stats['row_numbers'] = row_numbers
        
        # Count unique memory configurations
        memory_counts = {}
        for item in items:
            memory = getattr(item, 'memory', None)
            if memory:
                memory_counts[memory] = memory_counts.get(memory, 0) + 1
        if memory_counts:
            stats['memory_variations'] = memory_counts
        
        # Count unique storage configurations
        storage_counts = {}
        for item in items:
            storage = getattr(item, 'storage', None)
            if storage:
                storage_counts[storage] = storage_counts.get(storage, 0) + 1
        if storage_counts:
            stats['storage_variations'] = storage_counts
        
        # Count condition grades
        condition_counts = {}
        for item in items:
            condition = getattr(item, 'condition_grade', None)
            if condition:
                condition_counts[condition] = condition_counts.get(condition, 0) + 1
        if condition_counts:
            stats['condition_distribution'] = condition_counts
            
        return stats
            
    @staticmethod
    def _generate_group_statistics(items):
        """
        Generate statistical information about a group of manifest items
        
        Args:
            items: QuerySet of ManifestItem objects in the group
            
        Returns:
            dict: Statistical information about the group
        """
        stats = {}
        
        # Get row numbers if available
        row_numbers = []
        for item in items:
            if hasattr(item, 'row_number') and item.row_number:
                row_numbers.append(item.row_number)
            elif item.mapped_data and 'row_number' in item.mapped_data:
                row_numbers.append(item.mapped_data.get('row_number'))
        if row_numbers:
            stats['row_numbers'] = row_numbers
        
        # Count unique memory configurations
        memory_counts = {}
        for item in items:
            memory = getattr(item, 'memory', None)
            if memory:
                memory_counts[memory] = memory_counts.get(memory, 0) + 1
        if memory_counts:
            stats['memory_variations'] = memory_counts
        
        # Count unique storage configurations
        storage_counts = {}
        for item in items:
            storage = getattr(item, 'storage', None)
            if storage:
                storage_counts[storage] = storage_counts.get(storage, 0) + 1
        if storage_counts:
            stats['storage_variations'] = storage_counts
        
        # Count condition grades
        condition_counts = {}
        for item in items:
            condition = getattr(item, 'condition_grade', None)
            if condition:
                condition_counts[condition] = condition_counts.get(condition, 0) + 1
        if condition_counts:
            stats['condition_distribution'] = condition_counts
            
        return stats