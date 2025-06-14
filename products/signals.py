from django.db.models.signals import post_save
from django.dispatch import receiver
from products.models import ProductUnit
from warranties.models import Warranty
from django.db import transaction
from django.utils.timezone import now, timedelta

@receiver(post_save, sender=ProductUnit)
def create_warranty_on_sold(sender, instance, created, **kwargs):
    """
    Signal to create a warranty automatically when a ProductUnit is sold.
    Ensures warranty creation is atomic and avoids duplicates.
    """
    # Only create warranties for serialized products that are marked as sold
    if instance.status == 'sold' and instance.is_serialized:
        with transaction.atomic():
            # Ensure a warranty doesn't already exist for this unit
            if not Warranty.objects.filter(product_unit=instance).exists():
                # Create a basic 3-month temporary warranty
                Warranty.objects.create(
                    product_unit=instance,
                    order=instance.order_item.order if instance.order_item else None,
                    purchase_date=now().date(),
                    warranty_period=3,  # Default warranty period in months
                    status='not_registered',
                    warranty_expiration_date=now().date() + timedelta(days=90)  # 3 months
                )
