from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Warranty
from datetime import timedelta
from django.utils.timezone import now

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
