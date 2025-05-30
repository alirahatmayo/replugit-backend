from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List, Union
from django.utils import timezone
from orders.models import Order, OrderItem, OrderStatusHistory
from products.models import Product
from customers.models import Customer
import logging
from ..utils.price_formatter import PriceFormatter
from django.db import transaction

logger = logging.getLogger(__name__)

@dataclass
class ProcessedOrder:
    """Standardized order data structure"""
    order_number: str
    customer_name: str
    customer_order_id: str
    state: str
    relay_email: str
    phone_number: str
    order_date: datetime
    delivery_deadline: Optional[datetime]
    ship_date: Optional[datetime]
    address: Dict[str, str]
    items: List[Dict[str, Any]]
    platform_data: Dict[str, Any]

    def get(self, key, default=None):
        """Make the object act like a dictionary for backward compatibility"""
        return getattr(self, key, default)

class WalmartCAOrderProcessor:
    """Walmart CA order processor"""
    
    STATES = {
        'Created': 'created',
        'Acknowledged': 'acknowledged',
        'Shipped': 'shipped',
        'Delivered': 'delivered',
        'Cancelled': 'cancelled'
    }

    def process_order(self, data: Union[Dict[str, Any], ProcessedOrder]) -> ProcessedOrder:
        """Process raw order data or pass through already processed order"""
        # Debugging information
        print(f"Processing order data type: {type(data)}")
        if isinstance(data, dict):
            print(f"Keys in order data: {list(data.keys())}")
        elif hasattr(data, '__dict__'):
            print(f"Attributes in order object: {list(data.__dict__.keys())}")

        # Check if already a ProcessedOrder
        if isinstance(data, ProcessedOrder):
            return data
        
        # Add validation to ensure we have essential fields
        order_number = data.get('purchaseOrderId')
        if not order_number:
            logger.error("Missing required field: purchaseOrderId")
            logger.debug(f"Order data: {data}")
            return None  # Return None for orders missing essential fields
        
        # Only try to parse if it's a string and not already a dict
        if isinstance(data, str):
            try:
                import json
                data = json.loads(data)
                logger.debug("Converted string data to dictionary")
            except json.JSONDecodeError:
                logger.error(f"Error: Cannot parse order data: {data[:100]}...")
                raise ValueError(f"Invalid order data format: expected JSON object, got string")
        
        # No need for 'if order in data' - the data we're getting is directly an order object
        shipping = data.get('shippingInfo', {})
        address = shipping.get('postalAddress', {})

        return ProcessedOrder(
            order_number=order_number,
            customer_name=address.get('name', ''),
            customer_order_id=data.get('customerOrderId', ''),
            state=self._get_state(data),
            relay_email=data.get('customerEmailId', ''),
            phone_number=shipping.get('phone', ''),
            order_date=self._to_datetime(data.get('orderDate')),
            delivery_deadline=self._to_datetime(data.get('shippingInfo', {}).get('estimatedDeliveryDate')),
            ship_date=self._to_datetime(data.get('shippingInfo', {}).get('estimatedShipDate')),
            address=address,
            items=self._get_items(data),
            platform_data=data
        )

    @transaction.atomic
    def save_order(self, processed_order):
        """Save processed order to database using phone number as primary customer identifier"""
        try:
            phone_number = processed_order.phone_number
            
            print(f"Processing order: {processed_order.order_number} for phone: {phone_number}")
            
            # First check if this order already exists
            existing_order = Order.objects.filter(order_number=processed_order.order_number).first()
            
            if existing_order:
                print(f"Order {processed_order.order_number} already exists, skipping...")
                return existing_order
            
            # Find or update customer by phone number
            customer = None
            
            if phone_number:
                # Try to find customer by phone number
                customer = Customer.objects.filter(phone_number=phone_number).first()
                
                if customer:
                    # Update existing customer
                    print(f"Found existing customer by phone: {customer.name}")
                    self._update_customer_info(
                        customer=customer,
                        name=processed_order.customer_name,
                        relay_email=processed_order.relay_email,
                        address=processed_order.shipping_address
                    )
                else:
                    # Create new customer
                    print(f"Creating new customer with phone: {phone_number}")
                    customer = Customer.objects.create(
                        name=processed_order.customer_name,
                        phone_number=phone_number,
                        relay_email=processed_order.relay_email,
                        source_platform='walmart_ca',
                        is_active=True,
                        address=processed_order.shipping_address
                    )
            else:
                # No phone number, create customer based on whatever we have
                print(f"Creating customer without phone for order: {processed_order.order_number}")
                customer = Customer.objects.create(
                    name=processed_order.customer_name,
                    relay_email=processed_order.relay_email,
                    source_platform='walmart_ca',
                    is_active=True,
                    address=processed_order.shipping_address
                )
            
            # Create new order with the found/updated customer
            order = Order.objects.create(
                order_number=processed_order.order_number,
                customer=customer,
                platform=processed_order.platform,
                state=processed_order.state,
                order_date=processed_order.order_date,
                order_total=processed_order.order_total,
                shipping_address=processed_order.shipping_address,
                billing_address=processed_order.billing_address,
                platform_specific_data=processed_order.platform_specific_data
            )
            
            # Create order items
            # ... your existing item creation logic ...
            
            return order
            
        except Exception as e:
            logger.error(f"Error saving order {processed_order.order_number}: {e}", exc_info=True)
            print(f"Error saving order {processed_order.order_number}: {e}")
            raise
    
    def _update_customer_info(self, customer, name=None, relay_email=None, address=None):
        """Update customer information if it's changed or more complete"""
        updated = False
        
        # Update name if it's more complete than existing
        if name and len(name) > len(customer.name):
            customer.name = name
            updated = True
            print(f"Updated customer name to: {name}")
        
        # Always update relay email as it changes frequently
        if relay_email and relay_email != customer.relay_email:
            customer.relay_email = relay_email
            updated = True
        
        # Update address if provided and different
        if address and address != customer.address:
            customer.address = address
            updated = True
            print("Updated customer address")
            
        # Save changes if any were made
        if updated:
            customer.updated_at = timezone.now()
            customer.save()
            print(f"Saved updates for customer: {customer.name}")
            
        return customer

    def _get_state(self, data: Dict) -> str:
        """Extract order state with improved status determination"""
        # Get all line statuses and their quantities
        status_counts = {}
        total_quantity = 0
        
        order_lines = data.get('orderLines', {}).get('orderLine', [])
        if not order_lines:
            return 'created'
        
        # Count items in each status
        for line in order_lines:
            line_quantity = int(line.get('orderLineQuantity', {}).get('amount', '0'))
            line_statuses = line.get('orderLineStatuses', {}).get('orderLineStatus', [])
            for status_info in line_statuses:
                status = status_info.get('status')
                if status:
                    status_counts[status] = status_counts.get(status, 0) + line_quantity
                    total_quantity += line_quantity
        
        logger.debug(f"Order status counts: {status_counts}, Total quantity: {total_quantity}")
        
        # Logic for determining overall order status
        if 'Cancelled' in status_counts and status_counts['Cancelled'] == total_quantity:
            return 'cancelled'
        
        if 'Shipped' in status_counts:
            if status_counts['Shipped'] == total_quantity:
                return 'shipped'
            # Partial shipment
            return 'partially_shipped'
        
        if 'Acknowledged' in status_counts:
            return 'acknowledged'
        
        return 'created'

    def _get_items(self, data: Dict) -> List[Dict]:
        """Extract order items with proper price handling"""
        items = []
        for line in data.get('orderLines', {}).get('orderLine', []):
            item = line.get('item', {})
            charges = line.get('charges', {}).get('charge', [])
            
            # Format price data using centralized formatter
            price_data = PriceFormatter.format_price_data(charges)
            
            items.append({
                'sku': f"{item.get('sku')}",
                'name': item.get('productName', ''),
                'quantity': int(line.get('orderLineQuantity', {}).get('amount', '0')),
                'price_data': price_data
            })
            
            logger.info(
                f"Processed item: {item.get('sku')} - "
                f"Total: ${price_data['totals']['grand_total']}"
            )
        
        return items

    def _save_items(self, order: Order, items: List[Dict]) -> None:
        """Save order items"""
        logger.debug(f"Saving {len(items)} items for order {order.order_number}")
        for item in items:
            product = Product.objects.update_or_create(
                sku=item['sku'],
                defaults={'name': item['name']}
            )[0]

            order_item = OrderItem.objects.update_or_create(
                order=order,
                product=product,
                defaults={
                    'quantity': item['quantity'],
                    'price_data': item['price_data'],
                    'total_price': Decimal(item['price_data']['totals']['grand_total'])
                }
            )[0]
            logger.debug(f"Saved item: {product.name} ({order_item.quantity}x) - ${order_item.total_price}")

    def _to_datetime(self, timestamp: Optional[int]) -> Optional[datetime]:
        """Convert timestamp to datetime"""
        return timezone.make_aware(
            datetime.fromtimestamp(int(timestamp)/1000)
        ) if timestamp else None

    def get_order_line_numbers(self, data: Dict) -> List[str]:
        """Extract line numbers from order data for shipping/cancellation operations"""
        lines = []
        for line in data.get('orderLines', {}).get('orderLine', []):
            line_number = line.get('lineNumber')
            if line_number:
                lines.append(line_number)
        return lines
