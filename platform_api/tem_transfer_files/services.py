from django.db import transaction
from orders.models import Order, OrderItem
from products.models import Product
from customers.models import Customer
from .processors import get_processor

class OrderService:
    """Core service for processing platform orders (Walmart CA only)"""

    @staticmethod
    @transaction.atomic
    def process_order(platform: str, order_data: dict) -> Order:
        # Get standardized data using our Walmart CA processor.
        processor = get_processor(platform)
        std_data = processor.standardize_order_data(order_data)
        
        # Get or create customer
        customer, _ = Customer.objects.get_or_create(
            email=std_data['customer']['email'],
            defaults={
                'name': std_data['customer']['name'],
                'phone': std_data['customer']['phone']
            }
        )
        
        # Create or update order based on platform_order_id
        order, _ = Order.objects.update_or_create(
            platform_order_id=std_data['platform_order_id'],
            platform=platform,
            defaults={
                'customer': customer,
                'order_number': std_data['order_number'],
                'state': 'created',
                'platform_specific_data': std_data['platform_data']
            }
        )
        
        # Process order items
        for item_data in std_data['items']:
            product = Product.objects.get(sku=item_data['sku'])
            OrderItem.objects.update_or_create(
                order=order,
                product=product,
                defaults={
                    'quantity': item_data['quantity'],
                    'price_data': item_data['price_data']
                }
            )
        return order

    @staticmethod
    @transaction.atomic
    def update_order_status(platform: str, status_data: dict) -> Order:
        processor = get_processor(platform)
        std_data = processor.standardize_status_update(status_data)
        
        order = Order.objects.get(platform_order_id=std_data['platform_order_id'])
        order.transition_state(std_data['new_state'])
        return order
