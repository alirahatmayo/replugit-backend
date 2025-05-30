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
        validation_issues = []
        
        # Create a new receipt batch
        batch = ReceiptBatch(
            reference=f"Manifest #{manifest.manifest_number}",
            receipt_date=timezone.now(),
            location_id=location_id,
            notes=f"Auto-generated from Manifest: {manifest.manifest_number}",
            created_by_id=user_id,
            shipping_tracking=manifest.tracking_number,
            shipping_carrier=manifest.carrier,
            seller_info={
                "name": manifest.supplier_name,
                "manifest_id": manifest.id,
                "manifest_number": manifest.manifest_number,
                "manifest_date": manifest.date.isoformat() if manifest.date else None,
            },
            status="pending"
        )
        batch.save()
        
        # Process each manifest item into a batch item
        for manifest_item in manifest.items.all():
            cls._create_batch_item_from_manifest_item(
                batch, 
                manifest_item, 
                validation_issues
            )
        
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
        """
        # Get product family or report issue
        product_family = None
        product = None
        
        if manifest_item.product:
            product = manifest_item.product
            product_family = product.family
        elif manifest_item.product_family:
            product_family = manifest_item.product_family
        else:
            # Try to find by SKU
            if manifest_item.sku:
                try:
                    product = Product.objects.filter(sku=manifest_item.sku).first()
                    if product:
                        product_family = product.family
                except Exception as e:
                    validation_issues.append({
                        "item_id": manifest_item.id,
                        "severity": "warning",
                        "message": f"Error looking up product by SKU: {str(e)}"
                    })
            
            if not product_family and manifest_item.family_sku:
                try:
                    product_family = ProductFamily.objects.filter(sku=manifest_item.family_sku).first()
                except Exception as e:
                    validation_issues.append({
                        "item_id": manifest_item.id,
                        "severity": "warning",
                        "message": f"Error looking up product family by SKU: {str(e)}"
                    })
        
        if not product_family:
            validation_issues.append({
                "item_id": manifest_item.id,
                "severity": "error",
                "message": f"Could not determine product family for item {manifest_item.sku or manifest_item.family_sku or 'Unknown'}"
            })
            return None
        
        # Create the batch item
        batch_item = BatchItem(
            batch=batch,
            product_family=product_family,
            product=product,  # May be None, which is fine
            quantity=manifest_item.quantity,
            unit_cost=manifest_item.unit_cost,
            # Calculate total cost if unit cost available
            total_cost=manifest_item.unit_cost * manifest_item.quantity if manifest_item.unit_cost else None,
            notes=manifest_item.notes,
            # Default settings
            requires_unit_qc=manifest_item.requires_qc,
            create_product_units=True,
            source_type="manifest",
            source_id=str(manifest_item.id)
        )
        
        try:
            batch_item.save()
            return batch_item
        except Exception as e:
            validation_issues.append({
                "item_id": manifest_item.id,
                "severity": "error",
                "message": f"Failed to create batch item: {str(e)}"
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