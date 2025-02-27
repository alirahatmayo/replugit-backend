## customers/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from customers.models import Customer

@receiver(post_save, sender=Order)
def create_customer_on_order(sender, instance, created, **kwargs):
    if created and not instance.customer:
        Customer.objects.get_or_create(
            name=instance.customer_name or "Unknown",
            email=f"relay_{instance.order_number}@example.com"
        )

