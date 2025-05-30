import logging
from django.db import transaction
from django.utils import timezone

from ..models import Inventory, InventoryHistory, InventoryReceipt

logger = logging.getLogger(__name__)

class ReceiptService:
    """Service for inventory receipt operations"""
    
    @classmethod
    @transaction.atomic
    def create_receipt(cls, data, user):
        """Create inventory receipt and update inventory"""
        # Create receipt
        receipt = InventoryReceipt.objects.create(
            created_by=user,
            **data
        )
        
        # Update inventory
        inventory, created = Inventory.objects.get_or_create(
            product=receipt.product,
            location=receipt.location,
            defaults={'quantity': 0}
        )
        
        # Record history
        history = inventory.adjust_quantity(
            adjustment=receipt.quantity,
            reason="PURCHASE",
            reference=f"Receipt #{receipt.id}",
            notes=f"Inventory receipt from {receipt.get_seller_name() or 'unknown seller'}",
            user=user
        )
        
        # Generate units if needed
        units = []
        if receipt.should_create_product_units():
            units = receipt.generate_product_units()
            
        return receipt, inventory, history, units
        
    @classmethod
    @transaction.atomic
    def process_qc(cls, receipt, qc_data, user):
        """Process QC for units from a receipt"""
        from products.models import ProductUnit
        
        results = {'passed': 0, 'failed': 0, 'errors': []}
        processed_units = []
        
        for unit_data in qc_data:
            try:
                unit_id = unit_data.get('id')
                qc_result = unit_data.get('result')
                notes = unit_data.get('notes', '')
                
                if not unit_id or not qc_result:
                    results['errors'].append({
                        'unit': unit_id,
                        'error': 'Missing unit_id or result'
                    })
                    continue
                
                # Get the unit
                try:
                    unit = ProductUnit.objects.get(
                        id=unit_id,
                        status='pending_qc',
                        metadata__receipt_id=str(receipt.id)
                    )
                except ProductUnit.DoesNotExist:
                    results['errors'].append({
                        'unit': unit_id,
                        'error': 'Unit not found or not pending QC'
                    })
                    continue
                
                # Update unit status
                if qc_result.lower() == 'pass':
                    unit.status = 'in_stock'
                    results['passed'] += 1
                else:
                    unit.status = 'defective'
                    results['failed'] += 1
                
                # Update unit metadata
                unit.metadata = unit.metadata or {}
                if 'qc' not in unit.metadata:
                    unit.metadata['qc'] = {}
                    
                unit.metadata['qc']['result'] = qc_result.upper()
                unit.metadata['qc']['notes'] = notes
                unit.metadata['qc']['processed_at'] = timezone.now().isoformat()
                unit.metadata['qc']['processed_by'] = user.username
                
                unit.save()
                processed_units.append(unit)
                
            except Exception as e:
                results['errors'].append({
                    'unit': unit_data.get('id'),
                    'error': str(e)
                })
        
        # Update QC record if it exists
        qc_record = None
        try:
            qc_record = receipt.quality_control
            if qc_record:
                qc_record.status = 'COMPLETED'
                qc_record.inspected_by = user
                qc_record.inspected_at = timezone.now()
                qc_record.save()
        except Exception:
            # Quality control record might not exist
            pass
            
        return results, processed_units, qc_record