# orders/management/commands/fetch_orders.py

from django.core.management.base import BaseCommand
from platform_api.walmart_ca.api_client import WalmartCanadaAPIClient
from platform_api.walmart_ca.orders import WalmartOrders
import logging
from orders.models import Order, OrderItem
from customers.models import Customer
from products.models import Product
from datetime import datetime, timezone
from django.conf import settings 


# Import the utility function to extract price data
from .utils.walmart_ca_utils import extract_price_data
import json

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Fetch orders from Walmart Canada API and save them to the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--created_start_date",
            type=str,
            help="Start date for order creation in ISO 8601 format."
        )
        parser.add_argument(
            "--created_end_date",
            type=str,
            help="End date for order creation in ISO 8601 format."
        )
        parser.add_argument(
            "--order_id",
            type=str,
            help="Specific order ID to fetch."
        )
        parser.add_argument(
            "--action",
            type=str,
            choices=["fetch_orders", "fetch_by_id", "acknowledge", "cancel", "refund"],
            default="fetch_orders",
            help="Action to perform."
        )
        parser.add_argument(
            "--reason",
            type=str,
            help="Reason for order cancellation."
        )
        parser.add_argument(
            "--sub_reason",
            type=str,
            help="Sub-reason for order cancellation."
        )
        parser.add_argument(
            "--refund_data",
            type=str,
            help="JSON string for refund data."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the request details without making an API call."
        )

    def handle(self, *args, **kwargs):
        # Initialize your Walmart API client parameters.
        private_key = settings.WALMART_CA_CLIENT_SECRET
        client_id = settings.WALMART_CA_CLIENT_ID
        channel_type = settings.WALMART_CA_CHANNEL_TYPE
        client = WalmartCanadaAPIClient(client_id, private_key, channel_type)
        orders_api = WalmartOrders(client)

        action = kwargs.get("action")
        order_id = kwargs.get("order_id")
        created_start_date = kwargs.get("created_start_date")
        created_end_date = kwargs.get("created_end_date")
        dry_run = kwargs.get("dry-run")  # Note: use "dry-run" if defined with a hyphen

        if dry_run:
            self.stdout.write(f"Dry Run: {kwargs}")
            return

        try:
            if action == "fetch_orders":
                results = orders_api.fetch_orders(created_start_date, created_end_date)
                orders_list = (
                    results.get('list', {})
                           .get('elements', {})
                           .get('order', [])
                )
                for order_data in orders_list:
                    logger.info(f"Processing order: {order_data.get('purchaseOrderId')}")
                    self.save_order(order_data)
            elif action == "fetch_by_id":
                results = orders_api.fetch_order_by_id(order_id)
                self.save_order(results.get("order"))
            elif action == "acknowledge":
                orders_api.acknowledge_order(order_id)
            elif action == "cancel":
                orders_api.cancel_order(order_id, kwargs.get("reason"), kwargs.get("sub_reason"))
            elif action == "refund":
                orders_api.refund_order(order_id, kwargs.get("refund_data"))

            self.stdout.write(f"Action '{action}' completed successfully.")
        except Exception as e:
            logger.error(f"Error performing '{action}': {e}")
            self.stderr.write(f"Error: {e}")

    def save_order(self, order_data):
        if not order_data:
            raise ValueError("Order data is None")

        customer = self.get_or_create_customer(order_data)
        order = self.get_or_create_order(order_data, customer)
        self.save_order_items(order_data, order)

    def get_or_create_customer(self, order_data):
        relay_email = order_data.get('customerEmailId')
        shipping_info = order_data.get('shippingInfo', {})
        postal_address = shipping_info.get('postalAddress', {})
        customer_phone = shipping_info.get('phone')
        customer_name = postal_address.get('name')

        customer, _ = Customer.objects.update_or_create(
            phone_number=customer_phone,
            defaults={
                "name": customer_name,
                "relay_email": relay_email
            }
        )
        return customer

    def get_or_create_order(self, order_data, customer):
        order_number = order_data['purchaseOrderId']
        customer_order_id = order_data.get('customerOrderId', '')
        order_date = datetime.fromtimestamp(order_data['orderDate'] / 1000, timezone.utc)
        delivery_deadline = datetime.fromtimestamp(order_data['shippingInfo']['estimatedDeliveryDate'] / 1000, timezone.utc)
        shipping_deadline = datetime.fromtimestamp(order_data['shippingInfo']['estimatedShipDate'] / 1000, timezone.utc)

        # Get the order state from the first order line's status.
        state = (
            order_data['orderLines']
            ['orderLine'][0]
            ['orderLineStatuses']
            ['orderLineStatus'][0]
            ['status']
        )

        # Map key shipping details into a general, readable dictionary.
        shipping_info = order_data.get('shippingInfo', {})
        platform_specific_data = {
            "shipping_phone": shipping_info.get("phone"),
            "estimated_delivery_date": shipping_info.get("estimatedDeliveryDate"),
            "estimated_ship_date": shipping_info.get("estimatedShipDate"),
            "shipping_method": shipping_info.get("methodCode"),
            "postal_address": shipping_info.get("postalAddress", {})
        }

        order, _ = Order.objects.update_or_create(
            order_number=order_number,
            defaults={
                "customer": customer,
                "platform": "walmart_ca",
                "state": state.lower(),
                "order_date": order_date,
                "customer_order_id": customer_order_id,
                "platform_specific_data": platform_specific_data,
                "delivery_deadline": delivery_deadline,
                "ship_date": shipping_deadline,
            }
        )
        return order

    def save_order_items(self, order_data, order):
        order_lines = order_data.get('orderLines', {}).get('orderLine', [])
        for line in order_lines:
            self.process_order_line(line, order)

    def process_order_line(self, line, order):
        try:
            logger.info(f"Processing Order Line: {line.get('lineNumber')}")
            product, quantity, price_data, total_price = self.extract_product_details(line)
            # Create or update the order item without assigning any ProductUnits yet.
            order_item_defaults = {
                "quantity": quantity,
                "status": "pending",
                "price_data": price_data,
                "total_price": total_price,
            }
            order_item, created = OrderItem.objects.update_or_create(
                order=order,
                product=product,
                defaults=order_item_defaults,
            )
            logger.info(f"OrderItem {'created' if created else 'updated'}: {order_item}")
        except Exception as e:
            logger.error(f"Error processing order line: {e}")

    def extract_product_details(self, line):
        try:
            product_name = line['item']['productName']
            sku = line['item']['sku']
            quantity = int(line.get('orderLineQuantity', {}).get('amount', 0))

            # Use the utility function to extract price data
            price_data, total_price = extract_price_data(line)

            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={"name": product_name},
            )
            print (f"from the product name: {product_name} & sku: {sku}")
            return product, quantity, price_data, total_price
        except Exception as e:
            logger.error(f"Error extracting product details: {e}")
            # Return safe defaults if extraction fails.
            return None, 0, {}, 0.0



#--------------------------Commands--------------------------

# python manage.py fetch_orders_ca --created_start_date="2025-01-01" --action="fetch_orders"
# python manage.py fetch_orders_ca --order_id="123456789" --action="fetch_by_id"
# python manage.py fetch_orders_ca --order_id="123456789" --action="acknowledge"
# python manage.py fetch_orders_ca --order_id="123456789" --action="cancel" --reason="Out of stock" --sub_reason="Supplier delay"
# python manage.py fetch_orders_ca --order_id="123456789" --action="refund" --refund_data='{"refundAmount": 10.0, "refundReason": "Customer return"}' --dry-run
# python manage.py fetch_orders_ca --created_start_date="2022-01-01T00:00:00Z" --created_end_date="2022-01-31T23:59:59Z" --action="fetch_orders" --dry-run