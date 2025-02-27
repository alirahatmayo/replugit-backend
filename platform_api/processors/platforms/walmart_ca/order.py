# processor/platforms/walmart_ca/order.py
from datetime import datetime
from platform_api.processors.base.order import BaseOrderProcessor
from orders.models import Order, OrderItem
from products.models import Product
from typing import Dict, Any
from decimal import Decimal
from django.utils import timezone
import logging


logger = logging.getLogger(__name__)

class WalmartCAOrderProcessor(BaseOrderProcessor):
    """Walmart CA specific order processor"""

    def extract_customer_data(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract customer data from Walmart CA order data"""
        platform_data = order_data['platform_specific_data']
        shipping_info = platform_data['shippingInfo']
        address = shipping_info['postalAddress']
        # Get relay email from platform_specific_data
        relay_email = platform_data.get('customerEmailId')
        
        # Format address as JSON according to the model's requirements
        formatted_address = {
            'name': address.get('name', ''),
            'address1': address.get('address1', ''),
            'address2': address.get('address2', ''),
            'city': address.get('city', ''),
            'state': address.get('state', ''),
            'postalCode': address.get('postalCode', ''),
            'country': address.get('country', 'CA'),
            'addressType': address.get('addressType', '')
        }
        
        return {
            'name': address.get('name', ''),
            'phone_number': shipping_info.get('phone', ''),
            'source_platform': 'walmart_ca',
            'address': formatted_address,
            'relay_email': relay_email
        }

    def extract_order_data(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract order data according to the Order model fields"""
        platform_data = order_data['platform_specific_data']
        shipping_info = platform_data.get('shippingInfo', {})
        
        # Get order status from the first order line's status
        order_lines = platform_data.get('orderLines', {}).get('orderLine', [])
        walmart_status = 'Created'  # default status
        if order_lines:
            walmart_status = (order_lines[0]
                            .get('orderLineStatuses', {})
                            .get('orderLineStatus', [{}])[0]
                            .get('status', 'Created'))
        
        # Map Walmart status to our order state
        status_mapping = {
            'Created': 'created',
            'Acknowledged': 'processing',
            'Shipped': 'shipped',
            'Delivered': 'delivered',
            'Cancelled': 'cancelled'
        }
        state = status_mapping.get(walmart_status, 'created')
        
        order_date = self._process_timestamp(order_data['order_date'])
        delivery_deadline = self._process_timestamp(
            shipping_info.get('estimatedDeliveryDate')
        )
        ship_date = self._process_timestamp(
            shipping_info.get('estimatedShipDate')
        )
        
        return {
            'order_number': order_data['order_number'],
            'platform': 'walmart_ca',
            'customer_order_id': order_data['customer_order_id'],
            'order_date': order_date,
            'state': state,  # Add mapped state
            'platform_specific_data': order_data['platform_specific_data'],
            'delivery_deadline': delivery_deadline,
            'ship_date': ship_date,
            'order_total': Decimal('0.00')
        }

    def extract_product_data(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'sku': item_data['sku'],
            'name': item_data.get('productName', ''),
            'platform': 'walmart_ca'
        }

    def _extract_price_data(self, charges: list) -> tuple[Decimal, dict]:
        """Extract price and tax information from charges"""
        price_data = {}
        total_price = Decimal('0.00')
        
        for charge in charges:
            if charge.get('chargeType') == 'PRODUCT':
                amount = Decimal(str(charge.get('chargeAmount', {}).get('amount', '0.00')))
                total_price = amount
                price_data = {
                    'base_price': str(amount),
                    'currency': charge.get('chargeAmount', {}).get('currency', 'CAD'),
                    'tax_details': charge.get('tax', {}),
                }
                break
                
        return total_price, price_data

    def process_order_items(self, order: Order, order_data: Dict[str, Any]) -> None:
        """Process order items - status will be handled by model defaults"""
        order_lines = (order_data.get('platform_specific_data', {})
                      .get('orderLines', {})
                      .get('orderLine', []))

        for line in order_lines:
            # Create or update product
            product_data = self.extract_product_data(line['item'])
            product, _ = Product.objects.update_or_create(
                sku=product_data['sku'],
                defaults=product_data
            )

            # Process price data
            charges = line.get('charges', {}).get('charge', [])
            total_price, price_data = self._extract_price_data(charges)

            # Create or update order item
            OrderItem.objects.update_or_create(
                order=order,
                product=product,
                defaults={
                    'quantity': int(line['orderLineQuantity']['amount']),
                    'total_price': total_price,  # This field doesn't exist in the model
                    'price_data': price_data
                }
            )

    def _process_timestamp(self, timestamp: int) -> datetime:
        """Convert Walmart timestamp to timezone-aware datetime"""
        if not timestamp:
            return None
        return timezone.make_aware(
            datetime.fromtimestamp(int(timestamp)/1000)
        )