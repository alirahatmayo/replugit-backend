#processors/base/order.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from customers.models import Customer
from orders.models import Order, OrderItem
from products.models import Product
from datetime import datetime
import logging
from django.db import transaction

logger = logging.getLogger(__name__)

class BaseOrderProcessor(ABC):
    """Base class for platform-specific order processors"""

    @transaction.atomic
    def process_order(self, order_data: Dict[str, Any]) -> Order:
        """Template method to process an order"""
        try:
            # Extract customer data
            customer_data = self.extract_customer_data(order_data)
            customer = self.create_or_update_customer(customer_data)

            # Create or update order
            order = self.create_or_update_order(order_data, customer)

            # Process order items
            self.process_order_items(order, order_data)

            return order

        except Exception as e:
            logger.error(f"Error processing order: {e}", exc_info=True)
            raise

    @abstractmethod
    def extract_customer_data(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract customer data from order data"""
        pass

    @abstractmethod
    def extract_order_data(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract order data from raw data"""
        pass

    @abstractmethod
    def extract_product_data(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract product data from item data"""
        pass

    def create_or_update_customer(self, customer_data: Dict[str, Any]) -> Customer:
        """Create or update customer record"""
        customer, created = Customer.objects.update_or_create(
            phone_number=customer_data.get('phone_number'),
            defaults=customer_data
        )
        return customer

    def create_or_update_order(self, order_data: Dict[str, Any], customer: Customer) -> Order:
        """Create or update order record"""
        order_info = self.extract_order_data(order_data)
        order_info['customer'] = customer
        
        order, created = Order.objects.update_or_create(
            order_number=order_info['order_number'],
            # state=order_info['state'],
            # print(state)
            defaults=order_info
        )
        # print(state)
        return order

    @abstractmethod
    def process_order_items(self, order: Order, order_data: Dict[str, Any]) -> None:
        """Process order items"""
        pass

    def validate_order_data(self, order_data: Dict[str, Any]) -> None:
        required_fields = ['order_number', 'customer_order_id', 'order_date']
        missing = [f for f in required_fields if f not in order_data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")