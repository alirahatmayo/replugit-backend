from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.utils.timezone import now
from datetime import timedelta
from orders.models import OrderItem
from products.models import ProductUnit
from warranties.models import Warranty
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=OrderItem)
def handle_product_unit_assignment(sender, instance, created, **kwargs):
    """
    Signal to handle ProductUnit assignment and warranty creation when an OrderItem is shipped.
    """
    try:
        if instance.status == 'shipped':
            with transaction.atomic():
                # Get all assigned units for this order item
                assigned_units = instance.assigned_units.all()
                
                for unit in assigned_units:
                    if unit.is_serialized and unit.status == 'in_stock':
                        unit.status = 'shipped'
                        unit.save()

                        # Create or update warranty for each ProductUnit
                        warranty, created = Warranty.objects.get_or_create(
                            product_unit=unit,
                            defaults={
                                'purchase_date': instance.order.order_date,
                                'order': instance.order,
                                'warranty_period': 3,
                                'status': 'active',
                                'warranty_expiration_date': now() + timedelta(days=90),
                            },
                        )
                        if not created:
                            warranty.status = 'active'
                            warranty.warranty_expiration_date = now() + timedelta(days=90)
                            warranty.save()

                        logger.info(f"Created/Updated warranty for unit {unit.serial_number}")

    except Exception as e:
        logger.error(f"Error in product unit assignment for OrderItem ID {instance.id}: {e}")
        raise

