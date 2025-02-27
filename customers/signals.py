from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Customer, CustomerChangeLog


@receiver(pre_save, sender=Customer)
def track_customer_changes(sender, instance, **kwargs):
    """Track changes to customer records"""
    if instance.pk:  # Only track changes for existing customers
        try:
            old_customer = Customer.objects.get(pk=instance.pk)
            # Create changelog entry with old values
            CustomerChangeLog.objects.create(
                customer=instance,
                field_name='customer_update',
                old_value=str(old_customer.__dict__),
                new_value=str(instance.__dict__)
            )
        except Customer.DoesNotExist:
            pass  # New customer, no changes to track
