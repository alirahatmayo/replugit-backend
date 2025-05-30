from django.db import transaction
import logging

logger = logging.getLogger(__name__)

def mark_products_sold_by_order(order_id):
    """
    Mark all product units for a given order as sold.
    Returns the number of units updated.
    
    Args:
        order_id: The ID of the order to process
    
    Returns:
        int: Number of product units marked as sold
        
    Raises:
        ValueError: If order not found
    """
    from orders.models import Order
    
    try:
        order = Order.objects.get(id=order_id)
        count = 0
        
        with transaction.atomic():
            for item in order.items.all():
                for product_unit in item.assigned_units_relation.all():
                    try:
                        product_unit.mark_as_sold(order_item=item)
                        count += 1
                    except Exception as e:
                        logger.error(f"Error marking product unit {product_unit.id} as sold: {str(e)}")
                    
        return count
    except Order.DoesNotExist:
        logger.error(f"Order with ID {order_id} not found")
        raise ValueError(f"Order with ID {order_id} not found")

def mark_products_sold_by_order_number(order_number):
    """
    Mark all product units for a given order as sold, using order number.
    Returns the number of units updated.
    
    Args:
        order_number: The order number to process
        
    Returns:
        int: Number of product units marked as sold
        
    Raises:
        ValueError: If order not found
    """
    from orders.models import Order
    
    try:
        order = Order.objects.get(order_number=order_number)
        return mark_products_sold_by_order(order.id)
    except Order.DoesNotExist:
        logger.error(f"Order with number {order_number} not found")
        raise ValueError(f"Order with number {order_number} not found")

def assign_product_units_to_order_item(order_item_id, product_unit_ids):
    """
    Assign multiple product units to an order item.
    
    Args:
        order_item_id: The ID of the order item
        product_unit_ids: List of product unit IDs to assign
    
    Returns:
        int: Number of product units assigned
        
    Raises:
        ValueError: If order item or product units not found
    """
    from orders.models import OrderItem
    from products.models import ProductUnit
    
    try:
        order_item = OrderItem.objects.get(id=order_item_id)
        count = 0
        
        with transaction.atomic():
            for unit_id in product_unit_ids:
                try:
                    product_unit = ProductUnit.objects.get(id=unit_id)
                    product_unit.order_item = order_item
                    product_unit.save()
                    count += 1
                except ProductUnit.DoesNotExist:
                    logger.error(f"Product unit with ID {unit_id} not found")
                except Exception as e:
                    logger.error(f"Error assigning product unit {unit_id}: {str(e)}")
                    
        return count
    except OrderItem.DoesNotExist:
        logger.error(f"Order item with ID {order_item_id} not found")
        raise ValueError(f"Order item with ID {order_item_id} not found")

def reset_product_unit_status(product_unit_id, new_status='in_stock'):
    """
    Reset a product unit's status, typically after a return or cancellation.
    
    Args:
        product_unit_id: The ID of the product unit
        new_status: The new status to set (default: 'in_stock')
    
    Returns:
        bool: True if successful, False otherwise
    """
    from products.models import ProductUnit
    
    valid_statuses = ['in_stock', 'returned', 'defective', 'reserved', 'refurbished']
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")
    
    try:
        product_unit = ProductUnit.objects.get(id=product_unit_id)
        product_unit.status = new_status
        product_unit.save()
        
        # If moving back to stock, disassociate from order item
        if new_status in ['in_stock', 'refurbished']:
            product_unit.order_item = None
            product_unit.save()
            
        return True
    except ProductUnit.DoesNotExist:
        logger.error(f"Product unit with ID {product_unit_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error resetting product unit {product_unit_id}: {str(e)}")
        return False

def create_product_units(product_id, quantity=1):
    """
    Create multiple product units with unique serial numbers
    
    Args:
        product_id: ID of the product
        quantity: Number of units to create
        
    Returns:
        list: The created ProductUnit instances
    """
    from .models import Product, ProductUnit
    
    product = Product.objects.get(id=product_id)
    units = []
    
    for _ in range(quantity):
        unit = ProductUnit(
            product=product,
            status='in_stock',
            is_serialized=True
        )
        unit.save()  # This will auto-generate the serial number
        units.append(unit)
        
    return units