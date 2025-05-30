from django.db import transaction
from .models import Inventory, InventoryAdjustment

class InventoryService:
    """Service class for inventory operations"""
    
    @staticmethod
    @transaction.atomic
    def process_adjustment(adjustment, approver):
        """Process an inventory adjustment"""
        return adjustment.approve(approver)
    
    @staticmethod
    @transaction.atomic
    def apply_adjustment(inventory, quantity_change, reason, reference, notes, user):
        """Apply an inventory adjustment directly"""
        return inventory.adjust_quantity(
            adjustment=quantity_change,
            reason=reason,
            reference=reference, 
            notes=notes,
            user=user
        )
    
    @staticmethod
    @transaction.atomic
    def generate_product_units(receipt):
        """Generate product units for a receipt"""
        return receipt.generate_product_units()
    
    @staticmethod
    def create_receipt(product_family, quantity, location, reference=None, 
                      unit_cost=None, receipt_date=None, notes=None, 
                      create_product_units=True, requires_unit_qc=False,
                      product=None):
        """
        Create an inventory receipt
        
        This provides a service interface for other modules to create inventory
        receipts without direct model dependencies.
        """
        from .models import InventoryReceipt
        
        # Create the receipt
        receipt = InventoryReceipt.objects.create(
            product_family=product_family,
            product=product,
            quantity=quantity,
            location=location,
            reference=reference,
            unit_cost=unit_cost,
            receipt_date=receipt_date,
            notes=notes,
            create_product_units=create_product_units,
            requires_unit_qc=requires_unit_qc
        )
        
        return receipt
    
    @staticmethod
    def process_receipt(receipt):
        """
        Process an inventory receipt
        
        This provides a service interface for other modules to process inventory
        receipts without direct model dependencies.
        """
        return receipt.process_receipt()
    
    @staticmethod
    def update_product_stock(product, location, quantity_change, reference=None):
        """
        Update product stock levels
        
        This provides a service interface for other modules to update
        inventory levels without direct model dependencies.
        """
        from .models import InventoryTransaction
        
        transaction = InventoryTransaction.objects.create(
            product=product,
            location=location,
            quantity_change=quantity_change,
            reference=reference
        )
        
        return transaction.process_transaction()