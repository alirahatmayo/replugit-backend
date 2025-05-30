import logging
from django.db import transaction
from django.utils import timezone

from ..models import Inventory, InventoryHistory, InventoryAdjustment

logger = logging.getLogger(__name__)

class InventoryService:
    """Service for inventory operations"""
    
    @classmethod
    def update_inventory(cls, product, platform, location, new_quantity, reason, reference=None, notes=None, user=None):
        """Update inventory quantity with audit trail"""
        with transaction.atomic():
            # Get or create inventory record
            inventory, created = Inventory.objects.get_or_create(
                product=product,
                platform=platform,
                location=location,
                defaults={'quantity': 0}
            )
            
            # Adjust quantity
            adjustment = new_quantity - inventory.quantity
            history = inventory.adjust_quantity(
                adjustment=adjustment,
                reason=reason,
                reference=reference,
                notes=notes,
                user=user
            )
            
            # Update last sync time if this is from a platform sync
            if reason == 'SYNC':
                inventory.last_sync = timezone.now()
                inventory.save(update_fields=['last_sync'])
                
            return inventory, history
            
    @classmethod
    def process_adjustment(cls, adjustment, user):
        """Process an inventory adjustment"""
        if adjustment.status != 'PENDING':
            return False
            
        try:
            with transaction.atomic():
                # Apply the adjustment
                history = adjustment.inventory.adjust_quantity(
                    adjustment=adjustment.quantity_change,
                    reason=adjustment.reason,
                    reference=adjustment.reference,
                    notes=adjustment.notes,
                    user=user
                )
                
                # Update adjustment status
                adjustment.status = 'APPROVED'
                adjustment.approved_by = user
                adjustment.approved_at = timezone.now()
                adjustment.save(update_fields=['status', 'approved_by', 'approved_at'])
                
                return True
        except Exception as e:
            logger.error(f"Error processing adjustment {adjustment.id}: {e}", exc_info=True)
            return False

    @classmethod
    def get_low_stock_items(cls, threshold=None):
        """Get low stock inventory items"""
        queryset = Inventory.objects.filter(status='LOW_STOCK')
        
        if threshold:
            try:
                threshold = int(threshold)
                queryset = queryset.filter(quantity__lte=threshold)
            except ValueError:
                pass
                
        return queryset