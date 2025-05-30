"""
Manifest Batch Service

This service handles the creation of receipt batches from manifest data.
It converts grouped manifest items into batch items in the receiving system.
"""
import logging
from django.db import transaction
from django.utils import timezone
from manifest.models import Manifest, ManifestItem, ManifestGroup
from receiving.models import ReceiptBatch, BatchItem
from products.models import ProductFamily
from inventory.models import Location

logger = logging.getLogger(__name__)

class ManifestBatchService:
    """
    Service for converting manifest data to receiving batches.
    Handles the transformation of grouped manifest items into batch items
    and creates the necessary receiving batch records.
    """
    
    @staticmethod
    def create_batch_from_manifest(manifest_id, location_id, user=None, options=None):
        """
        Create a receiving batch from manifest data
        
        Args:
            manifest_id (int): ID of the manifest to convert
            location_id (int): ID of the location for the batch
            user (User): User creating the batch
            options (dict): Additional options for batch creation
            
        Returns:
            dict: Results of batch creation
            
        Raises:
            ValueError: If manifest is invalid or not ready
        """
        if options is None:
            options = {}
            
        # Retrieve objects and validate
        try:
            manifest = Manifest.objects.get(id=manifest_id)
            location = Location.objects.get(id=location_id)
        except Manifest.DoesNotExist:
            logger.error(f"Manifest with ID {manifest_id} not found")
            raise ValueError(f"Manifest with ID {manifest_id} not found")
        except Location.DoesNotExist:
            logger.error(f"Location with ID {location_id} not found")
            raise ValueError(f"Location with ID {location_id} not found")
            
        # Verify manifest status is ready for batch creation
        if manifest.status != 'grouped':
            raise ValueError(
                f"Manifest {manifest.name} is not ready for batch creation. "
                f"Current status: {manifest.status}, expected: grouped"
            )
            
        # Get groups from manifest
        groups = ManifestGroup.objects.filter(manifest=manifest)
        if not groups.exists():
            raise ValueError(f"Manifest {manifest.name} has no grouped items")
            
        # Create batch within a transaction
        with transaction.atomic():
            # Create the batch
            batch = ReceiptBatch.objects.create(
                reference=f"Manifest: {manifest.name}",
                location=location,
                created_by=user,
                notes=f"Created from manifest {manifest.id}: {manifest.name}",
                seller_info=options.get('seller_info', {})
            )
            
            # For each group, create a batch item
            batch_items_created = 0
            for group in groups:
                product_family = group.product_family
                
                if not product_family:
                    logger.warning(f"Group {group.id} has no product family assigned, skipping")
                    continue
                    
                # Get the total quantity from all items in the group
                items_in_group = ManifestItem.objects.filter(group=group)
                total_quantity = sum(item.quantity for item in items_in_group)
                
                # Create batch item
                batch_item = BatchItem.objects.create(
                    batch=batch,
                    product_family=product_family,
                    quantity=total_quantity,
                    unit_cost=options.get('unit_cost'),
                    notes=f"Created from manifest group {group.id}",
                    source_type='manifest',
                    source_id=str(manifest.id)
                )
                batch_items_created += 1
                
            # Update manifest status
            manifest.status = 'completed'
            manifest.save()
            
            # Return the results
            return {
                'batch': batch,
                'batch_id': batch.id,
                'batch_code': batch.batch_code,
                'items_created': batch_items_created,
                'manifest_id': manifest.id,
                'manifest_name': manifest.name
            }
            
    @staticmethod
    def get_batch_from_manifest(manifest_id):
        """
        Get receiving batch(es) created from a manifest
        
        Args:
            manifest_id (int): ID of the manifest
            
        Returns:
            QuerySet: BatchItems linked to this manifest
        """
        batch_items = BatchItem.objects.filter(
            source_type='manifest',
            source_id=str(manifest_id)
        ).select_related('batch')
        
        return batch_items