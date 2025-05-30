from django.db import transaction
from django.utils import timezone

class QualityControlService:
    """Service class for quality control business logic"""
    
    @staticmethod
    @transaction.atomic
    def process_inspection(qc, approved_qty, rejected_qty, notes, inspector):
        """Process QC inspection"""
        return qc.complete_inspection(approved_qty, rejected_qty, notes, inspector)
    
    @staticmethod
    @transaction.atomic
    def create_receipt_from_qc(qc, location, user, requires_unit_qc=False):
        """
        Create an inventory receipt from QC
        
        Args:
            qc: QualityControl object
            location: Location where items will be stored
            user: User creating the receipt
            requires_unit_qc: Whether individual units require QC
            
        Returns:
            Created InventoryReceipt object
        """
        # Create receipt and link to QC
        receipt = qc.create_inventory_receipt(location, user)
        
        # Set flag for unit-level QC if required
        receipt.requires_unit_qc = requires_unit_qc
        receipt.save()
        
        # Generate units
        units = receipt.generate_product_units()
        
        return receipt
    
    @staticmethod
    @transaction.atomic
    def perform_unit_qc(unit, test_data, user):
        """
        Perform QC on an individual unit
        
        Args:
            unit: ProductUnit object
            test_data: Dictionary with test results
            user: User performing QC
            
        Returns:
            ProductUnitQC object
        """
        from .models import ProductUnitQC, QualityControl
        
        # Get batch QC if it exists
        batch_qc = None
        if unit.metadata and 'qc' in unit.metadata and 'qc_id' in unit.metadata['qc']:
            qc_id = unit.metadata['qc']['qc_id']
            try:
                batch_qc = QualityControl.objects.get(pk=qc_id)
            except QualityControl.DoesNotExist:
                pass
        
        # Create QC record
        qc_record = ProductUnitQC.objects.create(
            unit=unit,
            batch_qc=batch_qc,
            tested_by=user,
            **test_data
        )
        
        return qc_record
    
    @staticmethod
    def create_qc_record_for_batch_item(batch_item):
        """
        Create a QC record for a batch item
        
        Args:
            batch_item: The batch item requiring QC
            
        Returns:
            The created QC record
        """
        from .models import QualityControlRecord
        
        # Create QC record
        qc_record = QualityControlRecord.objects.create(
            batch_item=batch_item,
            product_family=batch_item.product_family,
            product=batch_item.product,
            quantity=batch_item.quantity,
            location=batch_item.batch.location,
            reference=batch_item.batch.reference or f"Batch {batch_item.batch.batch_code}",
            status='pending'
        )
        
        return qc_record
    
    @staticmethod
    def complete_qc_process(qc_record, status, notes=None, user=None):
        """
        Complete a QC process with the given status
        
        Args:
            qc_record: The QC record to update
            status: One of 'passed', 'failed', or 'partially_passed'
            notes: Optional notes about the QC process
            user: The user who performed the QC
            
        Returns:
            The updated QC record
        """
        if status not in ['passed', 'failed', 'partially_passed']:
            raise ValueError("QC status must be 'passed', 'failed', or 'partially_passed'")
            
        qc_record.status = status
        if notes:
            qc_record.notes = notes
        if user:
            qc_record.completed_by = user
        qc_record.completed_at = timezone.now()
        qc_record.save()
        
        # If QC passed, create inventory receipt
        if status in ['passed', 'partially_passed']:
            # Get the quantity that passed QC
            passed_quantity = qc_record.quantity
            if status == 'partially_passed' and 'passed_quantity' in qc_record.metadata:
                passed_quantity = qc_record.metadata['passed_quantity']
                
            # Create inventory receipt for the passed quantity
            from inventory.models import InventoryReceipt
            from receiving.models import BatchItem
            
            batch_item = qc_record.batch_item
            if batch_item and passed_quantity > 0:
                receipt = InventoryReceipt.objects.create(
                    product_family=batch_item.product_family,
                    product=batch_item.product,
                    quantity=passed_quantity,
                    location=batch_item.batch.location,
                    reference=f"QC Passed: {batch_item.batch.reference or batch_item.batch.batch_code}",
                    unit_cost=batch_item.unit_cost,
                    receipt_date=timezone.now(),
                    notes=f"QC Notes: {qc_record.notes}" if qc_record.notes else "",
                    create_product_units=batch_item.create_product_units
                )
                
                # Link receipt to batch item if no receipt exists yet
                if not batch_item.inventory_receipt:
                    batch_item.inventory_receipt = receipt
                    batch_item.save(update_fields=['inventory_receipt'])
                
                # Process the receipt
                receipt.process_receipt()
        
        return qc_record