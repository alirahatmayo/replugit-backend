from .models import Warranty, WarrantyLog
from products.models import ProductUnit
from django.db import transaction
from datetime import timedelta
from django.utils.timezone import now
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

def create_or_update_warranty(product_unit, purchase_date, warranty_period=3):
    """Create or update a warranty for a given ProductUnit."""
    
    # Validate product integrity
    if product_unit.order_item and product_unit.product != product_unit.order_item.product:
        raise ValidationError(f"Product mismatch: unit product {product_unit.product} vs order item product {product_unit.order_item.product}")
    
    with transaction.atomic():
        warranty, created = Warranty.objects.get_or_create(
            product_unit=product_unit,
            
            defaults={
                'purchase_date': purchase_date,
                'warranty_period': warranty_period,
                'warranty_expiration_date': purchase_date + timedelta(days=30 * warranty_period),
                'status': 'not_registered',
            },
        )
        if not created:
            # Update expiration date if warranty exists but conditions have changed
            warranty.warranty_period = max(warranty.warranty_period, warranty_period)
            warranty.warranty_expiration_date = warranty.purchase_date + timedelta(days=30 * warranty.warranty_period)
            warranty.save()
        return warranty


def process_order_warranties(order):
    """
    Process warranties for all items in an order.

    Args:
        order: The Order instance whose items need warranty processing.
    """
    if not order:
        return
        
    with transaction.atomic():
        for item in order.items.select_related('product_unit').all():
            if hasattr(item, 'product_unit') and item.product_unit:
                create_or_update_warranty(
                    product_unit=item.product_unit,
                    purchase_date=order.order_date,
                )

def validate_warranty_activation(serial_number, activation_code):
    """
    Validate warranty activation credentials.
    
    Args:
        serial_number: Product serial number
        activation_code: Warranty activation code
    
    Returns:
        tuple: (is_valid, product_unit, error_message)
    """
    try:
        # Find product unit by serial number
        product_unit = ProductUnit.objects.get(serial_number=serial_number)
    except ProductUnit.DoesNotExist:
        logger.warning(f"Activation attempt for non-existent product: {serial_number}")
        return False, None, "No product found with this serial number."
    
    # Check if activation code exists
    if not product_unit.activation_code:
        logger.warning(f"Product unit {serial_number} has no activation code")
        return False, product_unit, "This product has no activation code assigned."
    
    # Validate the activation code (case-insensitive)
    if product_unit.activation_code.upper() != activation_code.upper():
        logger.warning(f"Invalid code for {serial_number}: expected {product_unit.activation_code}, got {activation_code}")
        return False, product_unit, "Invalid activation code for this serial number."
    
    # Additional validation to ensure product integrity
    if product_unit.order_item and product_unit.product != product_unit.order_item.product:
        logger.warning(f"Product mismatch for {serial_number}: unit product {product_unit.product} vs order item product {product_unit.order_item.product}")
        return False, product_unit, "Serial number belongs to a different product than expected."
    
    # Check if warranty already exists and is active
    try:
        warranty = Warranty.objects.get(product_unit=product_unit)
        if warranty.status == 'active':
            # This isn't an error - just information that it's already active
            logger.info(f"Warranty for {serial_number} is already active")
            # We return True since the activation credentials are valid
            # The view can decide how to handle already-active warranties
            return True, product_unit, "Warranty is already active for this product."
    except Warranty.DoesNotExist:
        # No warranty yet - that's fine for validation purposes
        pass
    
    return True, product_unit, None

def get_warranty_expiration_date(purchase_date, warranty_period):
    """
    Calculate warranty expiration date.
    
    Args:
        purchase_date: Date of purchase
        warranty_period: Warranty period in months
    
    Returns:
        date: Calculated expiration date
    """
    return purchase_date + timedelta(days=30 * warranty_period)

def bulk_process_warranties(order_ids):
    """
    Process warranties for multiple orders at once.
    Useful for scheduled tasks.
    
    Args:
        order_ids: List of order IDs to process
    
    Returns:
        dict: Results with success and error counts
    """
    from orders.models import Order
    
    success_count = 0
    error_count = 0
    
    for order_id in order_ids:
        try:
            order = Order.objects.get(id=order_id)
            process_order_warranties(order)
            success_count += 1
        except Exception as e:
            error_count += 1
            logger.error(f"Failed to process warranties for order {order_id}: {e}")
    
    return {
        'success_count': success_count,
        'error_count': error_count
    }

def create_warranty_from_order_item(order_item, product_unit, warranty_period=3):
    """
    Create a warranty with proper association between customer, order, and product unit.
    Ensures data integrity by validating relationships.
    
    Args:
        order_item: The OrderItem the product was sold through
        product_unit: The ProductUnit for which to create a warranty
        warranty_period: The warranty period in months
        
    Returns:
        Warranty: The created warranty
    
    Raises:
        ValidationError: If relationships are invalid
    """
    order = order_item.order
    customer = order.customer
    
    # Verify the product_unit is assigned to this order_item
    if product_unit not in order_item.assigned_units_relation.all():
        raise ValidationError(f"Product unit {product_unit} is not assigned to order item {order_item}")
    
    warranty = Warranty.objects.create(
        product_unit=product_unit,
        customer=customer,
        order=order,
        purchase_date=order.order_date or now().date(),
        warranty_period=warranty_period,
        status='not_registered'
    )
    
    return warranty
