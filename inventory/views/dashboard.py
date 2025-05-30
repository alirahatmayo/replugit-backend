from rest_framework.decorators import api_view
from django.db.models import Count, Sum, Q

from ..models import Inventory, InventoryHistory, InventoryReceipt
from ..serializers import InventoryReceiptSerializer
from ..utils import success_response

@api_view(['GET'])
def inventory_dashboard(request):
    """Get comprehensive inventory dashboard data for frontend"""
    # Get total inventory value and counts
    inventory_summary = Inventory.objects.aggregate(
        total_items=Count('id'),
        total_quantity=Sum('quantity'),
        low_stock_count=Count('id', filter=Q(status='LOW_STOCK')),
        out_of_stock_count=Count('id', filter=Q(status='OUT_OF_STOCK'))
    )
    
    # Get top products by quantity
    top_products = Inventory.objects.select_related('product', 'location').order_by('-quantity')[:10]
    top_products_data = [
        {
            'product_name': item.product.name,
            'product_sku': item.product.sku,
            'quantity': item.quantity,
            'status': item.status,
            'location': item.location.name,
            'product_id': str(item.product.id)
        }
        for item in top_products
    ]
    
    # Get recent activity
    recent_history = InventoryHistory.objects.select_related(
        'inventory__product', 'adjusted_by'
    ).order_by('-timestamp')[:20]
    
    recent_activity = [
        {
            'id': str(item.id),
            'product_name': item.inventory.product.name,
            'product_sku': item.inventory.product.sku,
            'change': item.change,
            'timestamp': item.timestamp,
            'reason': item.reason,
            'user': item.adjusted_by.username if item.adjusted_by else None,
            'reference': item.reference
        }
        for item in recent_history
    ]
    
    # Get recent receipts
    recent_receipts = InventoryReceipt.objects.select_related(
        'product', 'location', 'created_by'
    ).order_by('-receipt_date')[:10]
    
    receipts_data = [
        {
            'id': str(receipt.id),
            'product_name': receipt.product.name,
            'quantity': receipt.quantity,
            'location': receipt.location.name,
            'date': receipt.receipt_date,
            'reference': receipt.reference,
            'created_by': receipt.created_by.username if receipt.created_by else None
        }
        for receipt in recent_receipts
    ]
    
    # Return comprehensive dashboard data
    return success_response({
        'summary': inventory_summary,
        'top_products': top_products_data,
        'recent_activity': recent_activity,
        'recent_receipts': receipts_data,
        'status_counts': {
            'IN_STOCK': Inventory.objects.filter(status='IN_STOCK').count(),
            'LOW_STOCK': Inventory.objects.filter(status='LOW_STOCK').count(),
            'OUT_OF_STOCK': Inventory.objects.filter(status='OUT_OF_STOCK').count(),
            'DISCONTINUED': Inventory.objects.filter(status='DISCONTINUED').count()
        }
    })