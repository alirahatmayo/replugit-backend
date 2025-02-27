from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from django.utils import timezone
from orders.models import Order, OrderItem
from products.models import Product
from customers.models import Customer
import logging
from .utils.charge_calculator import ChargeCalculator
from .utils.price_formatter import PriceFormatter

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

class WalmartCAProcessor:
    """Walmart CA order processor"""
    
    STATES = {
        'Created': 'created',
        'Acknowledged': 'acknowledged',
        'Shipped': 'shipped',
        'Delivered': 'delivered',
        'Cancelled': 'cancelled'
    }

    def process_order(self, data: Dict[str, Any]) -> ProcessedOrder:
        """Process raw order data"""
        shipping = data.get('shippingInfo', {})
        address = shipping.get('postalAddress', {})

        return ProcessedOrder(
            order_number=data.get('purchaseOrderId'),
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

    def save_order(self, order: ProcessedOrder) -> Order:
        """Save order to database with status tracking"""
        try:
            # Check existing order status
            existing_order = Order.objects.filter(
                order_number=order.order_number,
                platform='walmart_ca'
            ).first()

            if existing_order and existing_order.state != order.state:
                logger.info(
                    f"Order {order.order_number} status changing from "
                    f"{existing_order.state} to {order.state}"
                )

            # Create/update customer
            customer = Customer.objects.update_or_create(
                phone_number=order.phone_number,
                defaults={
                    'name': order.customer_name,
                    'phone_number': order.phone_number,
                    'address': order.address,
                    'source_platform': 'walmart_ca',
                    'relay_email': order.relay_email,
                    'tags': ['walmart_ca']  # Added platform tag
                }
            )[0]

            # Create/update order with correct field names
            saved_order = Order.objects.update_or_create(
                order_number=order.order_number,
                platform='walmart_ca',
                defaults={
                    'customer': customer,
                    'state': order.state,
                    'order_date': order.order_date,
                    'platform_specific_data': order.platform_data,  # Changed from platform_data
                    'customer_order_id': order.customer_order_id,
                    'delivery_deadline': order.delivery_deadline,
                    'ship_date': order.ship_date
                }
            )[0]

            # Save items
            self._save_items(saved_order, order.items)

            logger.info(
                f"Saved order {saved_order.order_number} "
                f"(Status: {saved_order.state}, "
                f"Customer: {saved_order.customer.name})"
            )

            return saved_order

        except Exception as e:
            logger.error(f"Error saving order {order.order_number}: {str(e)}")
            raise

    def _get_state(self, data: Dict) -> str:
        """Extract order state with improved status determination"""
        order_lines = data.get('orderLines', {}).get('orderLine', [])
        print(f'order_lines in processor: {order_lines}')
        if not order_lines:
            return 'created'

        # Get all statuses from order lines
        statuses = []
        for line in order_lines:
            line_statuses = line.get('orderLineStatuses', {}).get('orderLineStatus', [])
            for status in line_statuses:
                statuses.append(status.get('status'))

        # Priority order for statuses
        priority_order = ['Cancelled', 'Delivered', 'Shipped', 'Acknowledged', 'Created']
        
        # Find the most significant status
        for priority_status in priority_order:
            if priority_status in statuses:
                logger.info(f"Order status determined as {priority_status} from statuses: {statuses}")
                return self.STATES.get(priority_status, 'created')
        
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
                'sku': f"CA-{item.get('sku')}",
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
        for item in items:
            product = Product.objects.update_or_create(
                sku=item['sku'],
                defaults={'name': item['name']},
                # product_type='product'
            )[0]

            OrderItem.objects.update_or_create(
                order=order,
                product=product,
                defaults={
                    'total_price': item['price_data']['totals']['grand_total'],
                    'quantity': item['quantity'],
                    'price_data': item['price_data']
                    # total_price will be calculated in the model's save method
                }
            )

    def _to_datetime(self, timestamp: Optional[int]) -> Optional[datetime]:
        """Convert timestamp to datetime"""
        return timezone.make_aware(
            datetime.fromtimestamp(int(timestamp)/1000)
        ) if timestamp else None
