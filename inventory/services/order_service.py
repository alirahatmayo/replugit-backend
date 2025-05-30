import logging
from django.db import transaction

from ..models import Inventory
from products.models import ProductUnit

logger = logging.getLogger(__name__)

class OrderService:
    """Service for order-related inventory operations"""
    
    @classmethod
    @transaction.atomic
    def allocate_units_to_order(cls, order_id, items, user):
        """Allocate inventory units to an order"""
        from orders.models import OrderItem
        
        results = {'success': [], 'errors': []}
        
        for item in items:
            try:
                item_id = item.get('order_item_id')
                product_id = item.get('product_id')
                quantity = item.get('quantity', 1)
                ignore_qc = item.get('ignore_qc', False)
                
                # Get the order item
                try:
                    order_item = OrderItem.objects.get(id=item_id)
                except OrderItem.DoesNotExist:
                    results['errors'].append({
                        'item_id': item_id,
                        'error': "Order item not found"
                    })
                    continue
                
                # Find available units of this product
                available_units = ProductUnit.objects.filter(
                    product_id=product_id,
                    status='in_stock'
                ).order_by('created_at')[:quantity]
                
                # Check if we have enough units
                if available_units.count() < quantity:
                    results['errors'].append({
                        'item_id': item_id,
                        'error': f"Not enough units available. Requested: {quantity}, Available: {available_units.count()}"
                    })
                    continue
                
                # Allocate each unit to the order item
                allocated_units = []
                for unit in available_units:
                    try:
                        unit.assign_to_order_item(
                            order_item=order_item,
                            user=user,
                            notes=f"Allocated to order {order_id}",
                            ignore_qc=ignore_qc
                        )
                        allocated_units.append(str(unit.id))
                    except Exception as e:
                        results['errors'].append({
                            'unit_id': str(unit.id),
                            'error': str(e)
                        })
                
                results['success'].append({
                    'item_id': item_id,
                    'product_id': product_id,
                    'allocated_count': len(allocated_units),
                    'allocated_units': allocated_units
                })
                
                # Update inventory reserved quantity
                inventory = Inventory.objects.filter(product_id=product_id).first()
                if inventory:
                    inventory.reserved_quantity = (inventory.reserved_quantity or 0) + len(allocated_units)
                    inventory.save()
                
            except Exception as e:
                results['errors'].append({
                    'item': item,
                    'error': str(e)
                })
                
        return results