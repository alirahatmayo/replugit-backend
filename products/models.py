# products/models.py

from django.db import models
from django.core.exceptions import ValidationError
import random
import string


# --------------------------
# Product Model
# --------------------------

class Product(models.Model):
    PLATFORM_CHOICES = [
        ('walmart_ca', 'Walmart Canada'),
        ('walmart_us', 'Walmart US'),
        ('amazon', 'Amazon'),
        ('shopify', 'Shopify'),
        ('bestbuy', 'BestBuy'),
        ('manual', 'Manual Entry'),
    ]

    name = models.CharField(max_length=255, help_text="Product name or title")
    sku = models.CharField(max_length=100, null=True, blank=True, help_text="Stock Keeping Unit")
    gtin = models.CharField(max_length=14, unique=True, null=True, blank=True, help_text="Global Trade Item Number")
    product_type = models.CharField(max_length=100, help_text="Product category or type")
    description = models.TextField(null=True, blank=True, help_text="Product description")
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES,
        help_text="Platform where the product was first fetched or imported."
    )
    platform_data = models.JSONField(default=dict, help_text="Platform-specific data for each platform")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        for platform, data in self.platform_data.items():
            if not isinstance(data, dict):
                raise ValidationError(f"Platform '{platform}' data must be a dictionary.")
            if platform == "walmart_ca" and "wpid" not in data:
                raise ValidationError("Walmart Canada data must include 'wpid'.")

    def __str__(self):
        return f"{self.name} (SKU: {self.sku}) - First fetched from {self.platform}"


# --------------------------
# ProductUnit Model
# --------------------------

STATUS_CHOICES = [
    ('in_stock', 'In Stock'),
    ('assigned', 'Assigned to Order'),
    ('sold', 'Sold or Shipped'),
    ('returned', 'Returned'),
    ('defective', 'Defective'),
]


def generate_activation_code(length=4):
    """
    Generate a simple 4-character alphanumeric activation code.
    """

    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

class ProductUnit(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="units"
    )
    serial_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    manufacturer_serial = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='in_stock')
    is_serialized = models.BooleanField(default=True, help_text="Whether the product unit is serialized.")
    # Active assignment: a product unit is assigned to at most one order item.
    activation_code = models.CharField(max_length=4, unique=True, null=True, blank=True)

    order_item = models.ForeignKey(
        'orders.OrderItem', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_units_relation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def product_name(self):
        return self.product.name

    def clean(self):
        # Call parent clean first.
        super().clean()
        
        # If the unit is assigned to an order item, perform additional checks.
        if self.order_item:
            # Check that the product matches the order item's product.
            if self.product != self.order_item.product:
                raise ValidationError("ProductUnit's product must match the product of its assigned OrderItem.")
            
            # Check that the number of units already assigned to this order item does not exceed the order quantity.
            # Exclude the current instance (if updating) from the count.
            current_count = self.__class__.objects.filter(order_item=self.order_item).exclude(pk=self.pk).count()
            if current_count >= self.order_item.quantity:
                raise ValidationError(
                    f"Cannot assign this ProductUnit because the order item already has {current_count} units, "
                    f"which meets/exceeds its quantity of {self.order_item.quantity}."
                )
            
    activation_code_cache = None

    def save(self, *args, **kwargs):
        # Call full_clean to enforce validations before saving.
        self.full_clean()
        
        # Detect changes and log them to the audit log (existing logic).
        if self.pk:
            old_self = ProductUnit.objects.get(pk=self.pk)
            if old_self.order_item != self.order_item:
                if old_self.order_item:
                    ProductUnitAssignmentHistory.objects.create(
                        product_unit=self,
                        order_item=old_self.order_item,
                        action='returned'
                    )
                if self.order_item:
                    ProductUnitAssignmentHistory.objects.create(
                        product_unit=self,
                        order_item=self.order_item,
                        action='assigned'
                    )
        else:
            if self.order_item:
                ProductUnitAssignmentHistory.objects.create(
                    product_unit=self,
                    order_item=self.order_item,
                    action='assigned'
                )
        if not self.activation_code:  # Generate only if not already set
            self.activation_code = generate_activation_code()
        super().save(*args, **kwargs)

    def unassign(self):
        """
        Unassign the product unit (e.g., when a unit is returned) and mark it as available.
        """
        self.order_item = None
        self.status = 'in_stock'
        self.save()

    def __str__(self):
        return f"{self.product.name} - {self.serial_number or 'No Serial'}"

# --------------------------
# ProductUnitAssignmentHistory Model
# --------------------------

class ProductUnitAssignmentHistory(models.Model):
    ACTION_CHOICES = (
        ('assigned', 'Assigned'),
        ('returned', 'Returned'),
        ('reassigned', 'Reassigned'),
    )
    product_unit = models.ForeignKey(
        ProductUnit, on_delete=models.CASCADE, related_name='assignment_history'
    )
    # order_item is nullable to support history entries for unassignment.
    order_item = models.ForeignKey(
        'orders.OrderItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='assignment_history'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    # Optionally, you can add a comments field to capture more context.
    comments = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.product_unit.serial_number} {self.get_action_display()} at {self.timestamp}"
