from rest_framework.decorators import api_view
from rest_framework import status

from ..models import InventoryReceipt
from products.models import ProductUnit
from ..utils import success_response, error_response

@api_view(['GET'])
def test_receipt_units(request, receipt_id):
    """
    Legacy endpoint to check if units were created for a receipt.
    Use /api/inventory/receipts/{id}/units/ for new integrations.
    """
    try:
        receipt = InventoryReceipt.objects.get(id=receipt_id)
        units = ProductUnit.objects.filter(metadata__receipt_id=str(receipt_id))
        
        return success_response({
            'receipt': {
                'id': str(receipt.id),
                'product': receipt.product.name,
                'quantity': receipt.quantity,
                'reference': receipt.reference
            },
            'units_created': units.count(),
            'units': [
                {
                    'id': str(unit.id),
                    'serial': unit.serial_number,
                    'status': unit.status
                }
                for unit in units
            ]
        })
    except InventoryReceipt.DoesNotExist:
        return error_response('Receipt not found', status_code=status.HTTP_404_NOT_FOUND)