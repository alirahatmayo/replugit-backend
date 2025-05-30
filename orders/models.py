# orders/models.py

from django.db import models
from django.core.exceptions import ValidationError
from customers.models import Customer
from products.models import Product  # Make sure this import works in your project
from datetime import datetime
from decimal import Decimal
from django.db.models import Sum
import logging
logger = logging.getLogger(__name__)
# from .utils import format_price_data, calculate_total_from_price_data, calculate_item_price, DecimalEncoder
import json
from django.utils import timezone

# --------------------------
# Order Model
# --------------------------

class Order(models.Model):
    ORDER_STATES = [
        ('created', 'Created'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('partially_returned', 'Partially Returned'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ]
    PLATFORM_CHOICES = [
        ('walmart_ca', 'Walmart Canada'),
        ('walmart_us', 'Walmart US'),
        ('amazon', 'Amazon'),
        ('shopify', 'Shopify'),
        ('bestbuy', 'BestBuy'),
        ('manual', 'Manual Entry'),
    ]
    order_number = models.CharField(max_length=100, unique=True, help_text="Internal unique order ID from platform.")
    customer_order_id = models.CharField(max_length=100, null=True, blank=True, help_text="Customer Order ID from the platform.")
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES, help_text="Platform where the order originated.")
    order_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Total order amount, including taxes and discounts.", default=0.0)
    order_date = models.DateTimeField(auto_now_add=True, help_text="Date when the order was created.")
    delivery_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for order delivery.")
    ship_date = models.DateTimeField(null=True, blank=True, help_text="Date the order was shipped.")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    state = models.CharField(max_length=20, choices=ORDER_STATES, default='created', help_text="Current order status.")
    platform_specific_data = models.JSONField(default=dict, blank=True, help_text="Platform-specific order details.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp for the last update to the order.")

    class Meta:
        indexes = [
            models.Index(fields=['platform'], name='idx_platform'),
            models.Index(fields=['state'], name='idx_state'),
            models.Index(fields=['order_date'], name='idx_order_date'),
            models.Index(fields=['customer'], name='idx_customer'),
        ]

    def clean(self):
        # Example: If an order is shipped, it must have tracking information.
        if self.state == 'shipped' and not self.platform_specific_data.get('tracking_info'):
            raise ValidationError("Shipped orders must have tracking information.")

    def transition_state(self, new_state):
        """
        Transition the order to a new state. When transitioning to 'returned',
        unassign all product units by marking them as 'in_stock' and clearing the assignment.
        """
        valid_transitions = {
            'created': ['confirmed', 'cancelled'],
            'confirmed': ['shipped', 'cancelled'],
            'shipped': ['delivered', 'returned'],
            'delivered': ['returned'],
            'returned': [],
            'cancelled': [],
        }
        if new_state not in valid_transitions.get(self.state, []):
            raise ValidationError(f"Cannot transition from {self.state} to {new_state}.")

        self.state = new_state
        self.save()

        # When returning, unassign all product units in all order items.
        if new_state == 'returned':
            for item in self.items.all():
                for unit in item.assigned_units.all():
                    unit.unassign()

    @property
    def calculate_total(self):
        """
        Calculate total by summing all associated OrderItem total_prices
        Returns Decimal(0) if no items exist
        """
        return sum((item.total_price or Decimal('0.00')) for item in self.items.all())

    def update_order_total(self):
        """Update order_total field with calculated total"""
        self.order_total = self.calculate_total
        self.save(update_fields=['order_total'])

    def __str__(self):
        return f"Order {self.order_number} ({self.platform}) - {self.state}"

    def update_status(self, new_status, reason=None, changed_by="system"):
        """Update order status and record the change in history"""
        if self.state == new_status:
            return False
        
        previous_status = self.state
        self.state = new_status
        self.save(update_fields=['state'])
        
        # Record status change in history
        OrderStatusHistory.objects.create(
            order=self,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            changed_by=changed_by
        )
        
        # Set temporary attributes for backward compatibility
        self._status_changed = True
        self._previous_status = previous_status
        
        return True

    def get_status_history(self):
        """Get status history in chronological order"""
        return self.status_history.all().order_by('changed_at')

    def get_latest_status_change(self):
        """Get the most recent status change"""
        return self.status_history.order_by('-changed_at').first()

# --------------------------
# OrderStatusHistory Model
# --------------------------

class OrderStatusHistory(models.Model):
    """Track order status changes"""
    order = models.ForeignKey('orders.Order', related_name='status_history', on_delete=models.CASCADE)
    previous_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    changed_at = models.DateTimeField(default=timezone.now)
    reason = models.TextField(null=True, blank=True)
    changed_by = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = "Order Status History"
        verbose_name_plural = "Order Status Histories"
    
    def __str__(self):
        return f"{self.order.order_number}: {self.previous_status} → {self.new_status}"

# --------------------------
# OrderItem Model
# --------------------------

class OrderItem(models.Model):
    STATUS_CHOICES = [('pending', 'Pending Assignment'), ('assigned', 'Assigned'), ('shipped', 'Shipped'), ('returned', 'Returned')]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", help_text="The parent order this item belongs to.")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, help_text="The product associated with this order item.")
    quantity = models.PositiveIntegerField(default=1, help_text="The quantity of the product in this order item.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', help_text="The current status of the order item.")
    price_data = models.JSONField(default=dict, blank=True, help_text="JSON field storing pricing and tax details for the item.")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="The total price of the item, including taxes.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="The timestamp when this item was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="The timestamp when this item was last updated.")

    class Meta:
        indexes = [
            models.Index(fields=['order'], name='idx_order'),
            models.Index(fields=['product'], name='idx_product'),
            models.Index(fields=['status'], name='idx_status'),
        ]
        # The unique constraint below prevents multiple order items for the same product in one order.
        constraints = [
            models.UniqueConstraint(fields=['order', 'product'], name='unique_product_per_order')
        ]

    def clean(self):
        if self.quantity < 1:
            raise ValidationError("Order item quantity must be at least 1.")

        # When units are expected (assigned/shipped/returned), validate the active assignments.
        if self.status in ['assigned', 'shipped', 'returned']:
            current_units = self.assigned_units.all()
            if current_units.count() != self.quantity:
                raise ValidationError(
                    f"Number of assigned units ({current_units.count()}) must equal order item quantity ({self.quantity})."
                )
            for unit in current_units:
                if unit.status != 'in_stock':
                    raise ValidationError(
                        f"ProductUnit {unit.serial_number} is not available for assignment (status: {unit.status})."
                    )
                if unit.product != self.product:
                    raise ValidationError(
                        f"ProductUnit {unit.serial_number} does not belong to {self.product.name}."
                    )

    def save(self, *args, **kwargs):
        if self.price_data:
            if isinstance(self.price_data, str):
                self.price_data = json.loads(self.price_data)
            
            # Use the totals from price_data directly
            self.total_price = Decimal(self.price_data['totals']['grand_total'])
    
        super().save(*args, **kwargs)
        self.order.update_order_total()

    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        # Update order total after deleting item
        order.update_order_total()

    @property
    def assigned_units(self):
        """
        Returns the ProductUnits currently assigned to this OrderItem.
        """
        return self.product.units.filter(order_item=self)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} unit{'s' if self.quantity > 1 else ''}"