from django.core.management.base import BaseCommand
from orders.models import Order

class Command(BaseCommand):
    help = 'Update all order totals based on their items'

    def handle(self, *args, **options):
        orders = Order.objects.prefetch_related('items').all()
        updated = 0

        for order in orders:
            old_total = order.order_total
            new_total = order.calculate_total
            
            if old_total != new_total:
                order.order_total = new_total
                order.save(update_fields=['order_total'])
                updated += 1
                self.stdout.write(
                    f"Updated Order #{order.order_number}: "
                    f"{old_total} → {new_total}"
                )

        self.stdout.write(
            self.style.SUCCESS(f"Updated {updated} order totals")
        )