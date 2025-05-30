from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from products.models import Product
from .models import Inventory, Location

@receiver(post_save, sender=Product)
def create_default_inventory(sender, instance, created, **kwargs):
    """Create default inventory records for new products"""
    if created:
        # Get default location or create one
        default_location, _ = Location.objects.get_or_create(
            code='DEFAULT',
            defaults={'name': 'Default Warehouse'}
        )
        
        # Create inventory record with zero quantity
        Inventory.objects.create(
            product=instance,
            location=default_location,
            quantity=0
        )