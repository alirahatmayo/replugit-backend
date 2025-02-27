import random
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from customers.models import Customer
from products.models import Product, ProductUnit
from orders.models import Order, OrderItem
from warranties.models import Warranty


class Command(BaseCommand):
    help = "Populate the database with extensive dummy data for testing"

    def handle(self, *args, **kwargs):
        # Clear existing data
        Warranty.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        ProductUnit.objects.all().delete()
        Product.objects.all().delete()
        Customer.objects.all().delete()

        self.stdout.write("Cleared existing data.")

        # Create dummy customers
        customers = []
        for i in range(20):
            customer = Customer.objects.create(
                name=f"Customer {i}",
                email=f"customer{i}@example.com",
                phone_number=f"12345678{i}",
                source_platform=random.choice(['amazon', 'walmart', 'shopify', 'bestbuy', 'manual']),
                is_active=random.choice([True, False]),
            )
            customers.append(customer)

        self.stdout.write("Created 20 dummy customers.")

        # Create dummy products
        products = []
        for i in range(10):
            product = Product.objects.create(
                product_name=f"Product {i}",
                category=f"Category {i % 3}",
            )
            products.append(product)

        self.stdout.write("Created 10 dummy products.")

        # Create dummy product units
        product_units = []
        for product in products:
            for j in range(10):
                product_unit = ProductUnit.objects.create(
                    product=product,
                    serial_number=f"SN-{product.id}-{j}",
                    manufacturer_serial=f"MSN-{product.id}-{j}",
                    status=random.choice(['in_stock', 'assigned', 'defective', 'returned']),
                )
                product_units.append(product_unit)

        self.stdout.write("Created 100 dummy product units.")

        # Create dummy orders and order items
        for i in range(20):
            customer = random.choice(customers)
            order = Order.objects.create(
                customer=customer,
                order_number=f"ORD-{i}",
                platform=random.choice(['amazon', 'walmart', 'shopify', 'bestbuy']),
                order_date=now().date() - timedelta(days=random.randint(1, 60)),
                shipping_date=now().date() - timedelta(days=random.randint(1, 30)),
                state=random.choice(['created', 'confirmed', 'shipped', 'cancelled']),
            )

            for _ in range(random.randint(1, 5)):
                product = random.choice(products)
                available_units = [unit for unit in product_units if unit.product == product and unit.status == 'in_stock']
                if available_units:
                    product_unit = random.choice(available_units)
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_unit=product_unit,
                        quantity=random.randint(1, 5),
                        status=random.choice(['assigned', 'shipped']),
                    )
                    product_unit.status = 'assigned'
                    product_unit.save()

        self.stdout.write("Created 20 dummy orders with items.")

        # Create dummy warranties
        for order in Order.objects.filter(state='shipped'):
            for item in order.items.all():
                if item.product_unit:
                    Warranty.objects.create(
                        product_unit=item.product_unit,
                        customer=order.customer,
                        order=order,
                        purchase_date=order.order_date,
                        warranty_period=random.choice([3, 6, 12]),
                        status=random.choice(['not_registered', 'active', 'expired']),
                        warranty_expiration_date=order.order_date + timedelta(days=30 * random.choice([3, 6, 12])),
                    )

        self.stdout.write("Created dummy warranties linked to orders.")

        self.stdout.write(self.style.SUCCESS("Extensive dummy data created successfully!"))
