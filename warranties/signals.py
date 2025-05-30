from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.utils.timezone import now
from .models import Warranty, WarrantyLog
from products.models import ProductUnit
from datetime import timedelta

@receiver(post_save, sender=Warranty)
def update_warranty_status_on_save(sender, instance, created, **kwargs):
    """
    Signal to handle warranty updates and status changes.
    Ensures warranties are activated or expired based on conditions.
    """
    with transaction.atomic():
        # Check for newly created warranties and set expiration date if missing
        if created and not instance.warranty_expiration_date:
            instance.warranty_expiration_date = instance.purchase_date + timedelta(days=30 * instance.warranty_period)
            instance.save()

        # Automatically expire warranties that are past their expiration date
        if instance.status == 'active' and instance.is_expired():
            instance.transition_status('expired')
            # Could add notification logic here

@receiver(pre_save, sender=Warranty)
def log_warranty_status_changes(sender, instance, **kwargs):
    """
    Log warranty status changes.
    """
    if instance.pk:  # Only for existing warranties
        try:
            old_instance = Warranty.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Create log entry for status change
                WarrantyLog.objects.create(
                    warranty=instance,
                    action=instance.status,
                    details=f"Status changed from {old_instance.status} to {instance.status}"
                )
        except Warranty.DoesNotExist:
            pass

@receiver(post_save, sender=ProductUnit)
def handle_product_unit_status_change(sender, instance, **kwargs):
    """
    When ProductUnit status changes, update related warranty.
    """
    if instance.status == 'returned':
        try:
            warranty = Warranty.objects.get(product_unit=instance)
            # Only reset active or not_registered warranties
            if warranty.status in ['active', 'not_registered']:
                warranty.reset_warranty(reason=f"Product unit marked as returned")
        except Warranty.DoesNotExist:
            pass
