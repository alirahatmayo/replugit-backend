from .models import Warranty
from django.db import transaction
from datetime import timedelta
from django.utils.timezone import now


def create_or_update_warranty(product_unit, purchase_date, warranty_period=3):
    """
    Create or update a warranty for a given ProductUnit.

    Args:
        product_unit: The ProductUnit instance associated with the warranty.
        purchase_date: The date the product was purchased.
        warranty_period: The initial warranty period in months (default is 3).

    Returns:
        Warranty: The created or updated warranty instance.
    """
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
    with transaction.atomic():
        for item in order.items.select_related('product_unit').all():
            if item.product_unit:
                create_or_update_warranty(
                    product_unit=item.product_unit,
                    purchase_date=order.order_date,
                )
