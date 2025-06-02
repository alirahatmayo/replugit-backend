from typing import Dict, List, Optional, Tuple, Any

from django.utils import timezone
from django.db import transaction
from django.conf import settings

from manifest.models import ManifestItem, Manifest
from receiving.models import ReceiptBatch, BatchItem
from inventory.models import Location
from products.models import ProductFamily, Product


class ManifestBatchService:
    """
    Service class for handling the conversion of manifests to receipt batches.
    Provides methods to create receipt batches from manifests for inventory receiving workflow.
    """
    
    @classmethod
    @transaction.atomic
    def create_receipt_batch_from_manifest(cls, manifest: Manifest, location_id: int, 
                                          user_id: Optional[int] = None) -> Tuple[ReceiptBatch, List[Dict]]:
        """
        Create a receipt batch from a manifest.
        
        Args:
            manifest: The Manifest object to convert to a receipt batch
            location_id: The location ID where items will be received
            user_id: Optional user ID of the person creating the batch
            
        Returns:
            Tuple containing:
            - The created ReceiptBatch object
            - List of validation issues/warnings encountered during batch creation
        """
        validation_issues = []        # Create a new receipt batch
        batch = ReceiptBatch(
            reference=f"Manifest #{manifest.id}" if not manifest.reference else manifest.reference,
            receipt_date=timezone.now(),
            location_id=location_id,
            notes=f"Auto-generated from Manifest: {manifest.name} (ID: {manifest.id})",
            created_by_id=user_id,
            seller_info={
                "name": manifest.name,  # Use manifest name as seller name
                "manifest_id": manifest.id,
                "manifest_reference": manifest.reference or f"Manifest #{manifest.id}",
                "manifest_uploaded_at": manifest.uploaded_at.isoformat() if manifest.uploaded_at else None,
            },
            status="pending"
        )
        batch.save()        # Process each manifest item into a batch item
        for manifest_item in manifest.items.all():
            try:
                batch_item = cls._create_batch_item_from_manifest_item(
                    batch, 
                    manifest_item, 
                    validation_issues
                )
                # Only continue if batch item was successfully created
                if batch_item is None:
                    continue
            except Exception as e:
                # Log the error but don't break the transaction
                validation_issues.append({
                    "item_id": manifest_item.id,
                    "severity": "error",
                    "message": f"Failed to process manifest item: {str(e)}"
                })
        
        # Update the manifest status
        manifest.status = "processing"
        manifest.save(update_fields=["status"])
        
        return batch, validation_issues
    @classmethod
    def _create_batch_item_from_manifest_item(
        cls, 
        batch: ReceiptBatch, 
        manifest_item: ManifestItem, 
        validation_issues: List[Dict]
    ) -> BatchItem:
        """
        Create a batch item from a manifest item.
        
        Args:
            batch: The parent ReceiptBatch
            manifest_item: The ManifestItem to convert
            validation_issues: List to append any validation issues to
            
        Returns:
            The created BatchItem
        """        # Get product family from the manifest item's group
        product_family = None
        try:
            # ManifestItem gets product family through its group
            if hasattr(manifest_item, 'group') and manifest_item.group and hasattr(manifest_item.group, 'product_family') and manifest_item.group.product_family:
                product_family = manifest_item.group.product_family
            elif hasattr(manifest_item, 'family_mapped_group') and manifest_item.family_mapped_group and hasattr(manifest_item.family_mapped_group, 'product_family') and manifest_item.family_mapped_group.product_family:
                product_family = manifest_item.family_mapped_group.product_family
        except Exception as e:
            validation_issues.append({
                "item_id": manifest_item.id,
                "severity": "warning",
                "message": f"Error accessing product family relationships: {str(e)}"
            })
        
        if not product_family:
            validation_issues.append({
                "item_id": manifest_item.id,
                "severity": "error",
                "message": f"Could not determine product family for item on row {manifest_item.row_number}. Item must be in a group with assigned product family."
            })
            return None
              # Create the batch item
        try:
            batch_item = BatchItem(
                batch=batch,
                product_family=product_family,
                product=None,  # ManifestItems don't have specific products, only families
                quantity=1,  # ARCHITECTURAL FIX: Each ManifestItem = 1 BatchItem with quantity=1
                unit_cost=manifest_item.unit_price if hasattr(manifest_item, 'unit_price') else None,  # Use unit_price field from ManifestItem
                # Calculate total cost if unit cost available
                total_cost=manifest_item.unit_price if hasattr(manifest_item, 'unit_price') and manifest_item.unit_price else None,
                notes=manifest_item.condition_notes if hasattr(manifest_item, 'condition_notes') else "",
                # Default settings
                requires_unit_qc=True,  # Default to requiring QC for manifest items
                create_product_units=True,
                source_type="manifest",
                source_id=str(manifest_item.id)
            )
        except Exception as e:
            validation_issues.append({
                "item_id": manifest_item.id,
                "severity": "error",
                "message": f"Failed to create BatchItem object: {str(e)}"
            })
            return None        # NEW: Preserve all ManifestItem details in item_details JSONField
        try:
            if hasattr(batch_item, 'set_details_from_manifest_item'):
                batch_item.set_details_from_manifest_item(manifest_item)
        except Exception as e:
            validation_issues.append({
                "item_id": manifest_item.id,
                "severity": "warning", 
                "message": f"Could not set item details: {str(e)}"
            })
        
        # Save the batch item
        try:
            batch_item.save()
            return batch_item
        except Exception as e:
            validation_issues.append({
                "item_id": manifest_item.id,
                "severity": "error",
                "message": f"Failed to save batch item: {str(e)}"
            })
            return None
    
    @classmethod
    def get_batch_from_manifest(cls, manifest: Manifest) -> Optional[ReceiptBatch]:
        """
        Find a receipt batch that was created from this manifest.
        
        Args:
            manifest: The Manifest to look up
            
        Returns:
            ReceiptBatch if found, None otherwise
        """
        # Look for a batch with seller_info containing this manifest's ID
        try:
            return ReceiptBatch.objects.filter(
                seller_info__manifest_id=manifest.id
            ).first()
        except Exception:
            return None
    
    @classmethod
    def update_manifest_status_from_batch(cls, manifest: Manifest) -> None:
        """
        Update the manifest status based on its related batch status.
        
        Args:
            manifest: The Manifest to update
        """
        batch = cls.get_batch_from_manifest(manifest)
        
        if not batch:
            return
        
        # Map batch status to manifest status
        status_map = {
            'pending': 'processing',
            'processing': 'processing',
            'completed': 'received',
            'cancelled': 'cancelled'
        }
        
        new_status = status_map.get(batch.status)
        if new_status and new_status != manifest.status:
            manifest.status = new_status
            manifest.save(update_fields=["status"])