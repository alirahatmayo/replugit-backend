from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework import status

from ..utils import success_response, error_response
from ..services.order_service import OrderService

@api_view(['POST'])
def allocate_units(request):
    """Allocate inventory units to an order"""
    order_id = request.data.get('order_id')
    items = request.data.get('items', [])
    
    if not order_id:
        return error_response("Missing order_id")
        
    if not items:
        return error_response("No items to allocate")
    
    try:
        # Use the service to perform allocation
        results = OrderService.allocate_units_to_order(
            order_id=order_id,
            items=items,
            user=request.user if request.user.is_authenticated else None
        )
        
        return success_response(results)
    
    except Exception as e:
        import logging
        logging.error(f"Error allocating units: {str(e)}", exc_info=True)
        return error_response(
            str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )