from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Q
from inventory.services import InventoryService

class ReceivingBatchService:
    """Service class for handling receipt batch operations"""
    
    @classmethod
    def _create_inventory_receipt(cls, batch_item, batch):
        """
        Create an inventory receipt for a batch item.
        Extracted for better maintainability and future dependency inversion.
        """
        # Use InventoryService instead of directly creating model
        return InventoryService.create_receipt(
            product_family=batch_item.product_family,
            product=batch_item.product,
            quantity=batch_item.quantity,
            location=batch.location,
            reference=batch.reference or f"Batch {batch.batch_code}",
            unit_cost=batch_item.unit_cost,
            receipt_date=batch.receipt_date,
            notes=batch_item.notes or batch.notes,
            create_product_units=batch_item.create_product_units,
            requires_unit_qc=batch_item.requires_unit_qc
        )
    
    @classmethod
    def process_batch(cls, batch):
        """
        Process all unprocessed receipts in this batch.
        
        For items that don't require QC, create inventory receipts immediately.
        For items that require QC, create QC records but delay inventory receipts.
        """
        # Use service layer to communicate with inventory system
        from inventory.services import InventoryService
        from quality_control.services import QualityControlService
        
        processed_count = 0
        
        # Update batch status to processing
        batch.status = 'processing'
        batch.save(update_fields=['status'])
        
        # Process all unprocessed items
        for item in batch.items.all():
            if item.is_processed:
                continue
                
            if item.skip_inventory_receipt:
                # Mark as processed without creating a receipt
                processed_count += 1
                item.is_processed = True
                item.save(update_fields=['is_processed'])
                continue
                
            # If item requires QC, create QC record but no inventory receipt yet
            if item.requires_unit_qc:
                QualityControlService.create_qc_record_for_batch_item(item)
                continue
            
            # For items not requiring QC, create inventory receipt immediately
            receipt = cls._create_inventory_receipt(item, batch)
            
            # Link receipt to batch item
            item.inventory_receipt = receipt
            item.save(update_fields=['inventory_receipt'])
            
            # Process the receipt
            InventoryService.process_receipt(receipt)
            processed_count += 1
        
        # Check if all items are processed or being processed in QC
        if cls.is_batch_fully_handled(batch):
            batch.status = 'completed'
            batch.completed_at = timezone.now()
            batch.save(update_fields=['status', 'completed_at'])
        
        return processed_count > 0
    
    @staticmethod
    def is_batch_fully_handled(batch):
        """
        Check if a batch is fully handled (all items are either processed or in QC)
        """
        for item in batch.items.all():
            # Skip items that don't need inventory receipts
            if item.skip_inventory_receipt:
                continue
                
            # If item requires QC, check if QC record exists
            if item.requires_unit_qc:
                from quality_control.models import QualityControlRecord
                if not QualityControlRecord.objects.filter(batch_item=item).exists():
                    return False
                continue
                
            # For regular items, check if inventory receipt is processed
            if not item.is_processed:
                return False
                
        return True
    
    @staticmethod
    def calculate_totals(batch):
        """
        Calculate total cost and quantity from all batch items.
        
        Args:
            batch: The ReceiptBatch instance
            
        Returns:
            dict: Dictionary with total_cost and total_items
        """
        # Use aggregate to sum all batch items
        totals = batch.items.aggregate(
            total_cost=Sum('total_cost'),
            total_items=Sum('quantity')
        )
        
        batch.total_cost = totals['total_cost'] or 0
        batch.save(update_fields=['total_cost'])
        
        return {
            'total_cost': batch.total_cost,
            'total_items': totals['total_items'] or 0
        }
    
    @staticmethod
    def is_batch_processed(batch):
        """
        Check if the batch is fully processed.
        
        A batch is considered processed if:
        1. It has at least one item (empty batches aren't processed)
        2. All items that need processing have been processed
        
        Args:
            batch: The ReceiptBatch instance
            
        Returns:
            bool: True if the batch is processed, False otherwise
        """
        # Must have at least one item
        if batch.items.count() == 0:
            return False
            
        # Check for any unprocessed items
        return ReceivingBatchService.get_unprocessed_items(batch).count() == 0
    
    @staticmethod
    def get_unprocessed_items(batch):
        """
        Get all batch items that need processing.
        
        Returns items that:
        1. Don't have skip_inventory_receipt=True
        2. Either have no inventory receipt or have an unprocessed one
        
        Args:
            batch: The ReceiptBatch instance
            
        Returns:
            QuerySet: Filtered queryset of BatchItem instances
        """
        return batch.items.filter(
            Q(skip_inventory_receipt=False) & 
            Q(
                Q(inventory_receipt__isnull=True) | 
                Q(inventory_receipt__is_processed=False)
            )
        )
    
    @staticmethod
    def get_processable_items(batch):
        """
        Get batch items that can be processed right now.
        
        Returns items that:
        1. Have an inventory receipt
        2. That receipt is not yet processed
        
        Args:
            batch: The ReceiptBatch instance
            
        Returns:
            QuerySet: Filtered queryset of BatchItem instances
        """
        return batch.items.filter(
            inventory_receipt__isnull=False,
            inventory_receipt__is_processed=False
        )
    
    @staticmethod
    def has_skipped_items_only(batch):
        """
        Check if this batch only has items that are marked to skip inventory receipt.
        
        Returns True if:
        1. There are no items that need to create inventory receipts
        2. There are only items with skip_inventory_receipt=True
        
        Args:
            batch: The ReceiptBatch instance
            
        Returns:
            bool: True if all items are skipped, False otherwise
        """
        return (
            batch.items.filter(skip_inventory_receipt=False).count() == 0 and
            batch.items.count() > 0
        )
    
    @staticmethod
    def mark_as_completed(batch):
        """
        Mark this batch as completed with timestamp.
        
        Args:
            batch: The ReceiptBatch instance
            
        Returns:
            bool: True to indicate success
        """
        batch.status = 'completed'
        batch.completed_at = timezone.now()
        batch.save(update_fields=['status', 'completed_at'])
        return True

    @classmethod
    def create_batch_from_manifest(cls, manifest, location_id, created_by=None):
        """
        Create a receipt batch from a manifest.
        
        Args:
            manifest: Manifest instance
            location_id: ID of the location for the batch
            created_by: User who is creating the batch
            
        Returns:
            ReceiptBatch: Created batch
        """
        from .models import ReceiptBatch, BatchItem
        from manifest.services import ManifestGroupingService
        
        with transaction.atomic():
            # Create batch
            batch = ReceiptBatch.objects.create(
                reference=manifest.reference or f"Manifest {manifest.id}",
                location_id=location_id,
                notes=manifest.notes,
                created_by=created_by or manifest.uploaded_by
            )
            
            # Link manifest to batch
            manifest.receipt_batch = batch
            manifest.status = 'processing'
            manifest.save(update_fields=['receipt_batch', 'status'])
            
            # Group manifest items if not already grouped
            if not manifest.groups.exists():
                ManifestGroupingService.group_similar_items(manifest.id)
                
            # Process each group as a batch item
            groups = manifest.groups.all()
            
            for group in groups:
                # Create batch item
                batch_item = BatchItem.objects.create(
                    batch=batch,
                    product_family=group.product_family,
                    quantity=group.quantity,
                    unit_cost=group.unit_price,
                    notes=group.notes,
                    requires_unit_qc=(group.condition_grade != 'A')  # Require QC for non-A grade items
                )
                
                # Link group to batch item
                group.batch_item = batch_item
                group.save(update_fields=['batch_item'])
                
                # Link manifest items to batch item
                manifest.items.filter(group=group).update(
                    batch_item=batch_item,
                    status='processed',
                    processed_at=timezone.now()
                )
            
            # Update manifest status
            manifest.status = 'completed'
            manifest.completed_at = timezone.now()
            manifest.save(update_fields=['status', 'completed_at'])
            
            # Calculate batch totals
            cls.calculate_totals(batch)
            
            return batch


class BatchItemService:
    """Service for managing individual batch items"""
    
    @staticmethod
    def validate_product_compatibility(product, product_family):
        """Validate that a product belongs to the given product family"""
        if not product or not product_family:
            return True
        
        return product.family_id == product_family.id
    
    @staticmethod
    def process_batch_item(batch_item):
        """Process a single batch item"""
        if batch_item.is_processed:
            return False
            
        if batch_item.skip_inventory_receipt:
            return True
            
        # Create inventory receipt if needed
        if not batch_item.inventory_receipt:
            batch = batch_item.batch
            receipt = ReceivingBatchService._create_inventory_receipt(batch_item, batch)
            
            batch_item.inventory_receipt = receipt
            batch_item.save(update_fields=['inventory_receipt'])
            
        # Process the receipt if needed
        if not batch_item.inventory_receipt.is_processed:
            from inventory.services import InventoryService
            InventoryService.process_receipt(batch_item.inventory_receipt)
            
        return True