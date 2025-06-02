# products/models.py

from django.db import models
from django.core.exceptions import ValidationError
import random
import string
from django.db import transaction

# Product Type Choices
PRODUCT_TYPE_CHOICES = [
    ('laptop', 'Laptop'),
    ('desktop', 'Desktop'),
    ('server', 'Server'),
    ('tablet', 'Tablet'),
    ('phone', 'Smartphone'),
    ('monitor', 'Monitor'),
    ('printer', 'Printer'),
    ('networking', 'Networking Equipment'),
    ('accessory', 'Accessory'),
    ('peripheral', 'Peripheral'),
    ('component', 'Component'),
    ('storage', 'Storage Device'),
    ('software', 'Software'),
    ('other', 'Other')
]

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
    family = models.ForeignKey('ProductFamily', on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    sku = models.CharField(max_length=100, null=True, blank=True, help_text="Stock Keeping Unit")
    gtin = models.CharField(max_length=14, unique=True, null=True, blank=True, help_text="Global Trade Item Number")
    product_type = models.CharField(max_length=100, help_text="Product category or type")
    description = models.TextField(null=True, blank=True, help_text="Product description")
    platform = models.CharField(max_length=50,choices=PLATFORM_CHOICES,help_text="Platform where the product was first fetched or imported.",default='manual')
    price_data = models.JSONField(default=dict, help_text="Price data for each platform", blank=True)
    platform_data = models.JSONField(default=dict, help_text="Platform-specific data for each platform", blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata about this product")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    regular_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_primary_listing = models.BooleanField(default=False, 
                                             help_text="Whether this is the primary listing for this product family")

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

def generate_serial(product):
    """
    Generate a simple 6-character serial number with format:
    [Category Prefix (1)][Random Alphanumeric (5)]
    
    Example: A12XY9
    """
    import random
    import string
    
    # Get category prefix (first letter of product type or X if none)
    if product.product_type and len(product.product_type) > 0:
        prefix = product.product_type[0].upper()
    else:
        prefix = 'X'
    
    # Generate 5 random alphanumeric characters
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=5))
    
    # Combine prefix and random part
    serial = f"{prefix}{random_part}"
    
    # Check if this serial already exists - if so, try again
    if ProductUnit.objects.filter(serial_number=serial).exists():
        return generate_serial(product)
        
    return serial

class ProductUnit(models.Model):
    STATUS_CHOICES = (
        ('pending_qc', 'Pending Quality Control'),
        ('in_stock', 'In Stock'),
        ('allocated', 'Allocated'),
        ('shipped', 'Shipped'),
        ('sold', 'Sold'),
        ('returned', 'Returned'),
        ('defective', 'Defective'),
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="units")
    serial_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    manufacturer_serial = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock')
    is_serialized = models.BooleanField(default=True, help_text="Whether the product unit is serialized.")
    activation_code = models.CharField(max_length=4, unique=True, null=True, blank=True)
    batch_code = models.CharField(max_length=50, blank=True, null=True, help_text="Batch identifier for grouped units")
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_units_relation")
    location = models.ForeignKey('inventory.Location', on_delete=models.SET_NULL, null=True, blank=True, related_name='stored_units')
    location_details = models.JSONField(default=dict,blank=True,help_text="Detailed location information (shelf, bin, etc.)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(
        null=True, 
        blank=True,
        help_text="Additional metadata about this unit (receipt info, seller, etc)"
    )

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
        
        # Generate serial number if not provided
        if not self.serial_number:
            self.serial_number = generate_serial(self.product)
        
        # Generate activation code if not provided
        if not self.activation_code:
            self.activation_code = generate_activation_code()
        
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
                
        super().save(*args, **kwargs)

    def unassign(self):
        """
        Unassign the product unit (e.g., when a unit is returned) and mark it as available.
        """
        self.order_item = None
        self.status = 'in_stock'
        self.save()

    def mark_as_sold(self, order_item=None):
        """
        Mark this product unit as sold.
        This will trigger warranty creation via the signal.
        """
        if order_item:
            self.order_item = order_item
        self.status = 'sold'
        self.save()

    def update_location(self, location=None, **details):
        """Update unit location with detailed tracking"""
        if location:
            self.location = location
            # Add location.name to details for consistency
            details['location_name'] = location.name
        
        # Update or add new details, preserving existing ones
        if self.location_details:
            self.location_details.update(details)
        else:
            self.location_details = details
        
        self.save()

    @property
    def needs_qc(self):
        """Check if unit needs QC"""
        return self.status == 'pending_qc'
    
    @property
    def has_completed_qc(self):
        """Check if QC is complete"""
        return hasattr(self, 'qc_details')

    def __str__(self):
        return f"{self.product.name} - {self.serial_number or 'No Serial'}"

    @transaction.atomic
    def assign_to_order_item(self, order_item, user=None, notes=None, ignore_qc=False):
        """
        Assign this unit to an order item
        
        Args:
            order_item: The OrderItem to assign this unit to
            user: User making the assignment
            notes: Optional notes about the assignment
            ignore_qc: Set to True to allow assignment of pending_qc units
            
        Returns:
            True if successful
            
        Raises:
            ValidationError if the unit cannot be assigned
        """
        from django.core.exceptions import ValidationError
        
        # Status validation
        if self.status == 'defective':
            raise ValidationError("Cannot assign defective units to orders")
            
        if self.status == 'pending_qc' and not ignore_qc:
            raise ValidationError(
                "This unit is awaiting quality control and cannot be assigned. "
                "Pass ignore_qc=True to force assignment."
            )
        
        # Store previous values for history
        previous_status = self.status
        previous_order_item = self.order_item
        
        # Update unit
        self.status = 'allocated'
        self.order_item = order_item
        self.save(update_fields=['status', 'order_item', 'updated_at'])
        
        # Create history record with QC warning note if applicable
        comments = notes or ""
        if previous_status == 'pending_qc':
            comments += " (WARNING: Assigned while pending quality control)"
            
        ProductUnitAssignmentHistory.objects.create(
            product_unit=self,
            order_item=order_item,
            previous_order_item=previous_order_item,
            action=f"ALLOCATED_{previous_status}",
            comments=comments,
            created_by=user
        )
        
        return True

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


# --------------------------
# ProductUnitLocationHistory Model
# --------------------------

class ProductUnitLocationHistory(models.Model):
    product_unit = models.ForeignKey(ProductUnit, on_delete=models.CASCADE, related_name='location_history')
    previous_location = models.ForeignKey('inventory.Location', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    new_location = models.ForeignKey('inventory.Location', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    previous_details = models.JSONField(default=dict, blank=True)
    new_details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        prev = self.previous_location.name if self.previous_location else "None"
        new = self.new_location.name if self.new_location else "None"
        return f"{self.product_unit.serial_number}: {prev} → {new} at {self.timestamp}"


# --------------------------
# ProductFamily Model
# --------------------------

class ProductFamily(models.Model):
    """
    Groups related products for inventory aggregation.
    A product family represents a set of products that share common attributes,
    such as manufacturer and model.
    """
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, help_text="Base SKU for this family")
    description = models.TextField(blank=True, null=True)
    manufacturer = models.CharField(max_length=255, null=True, blank=True)
    model = models.CharField(max_length=255, null=True, blank=True)
    product_type = models.CharField(max_length=100, choices=PRODUCT_TYPE_CHOICES, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Additional attributes stored as JSON
    attributes = models.JSONField(default=dict, blank=True, 
                                help_text="Product family attributes like processor, screen size, etc.")
    
    # For category-based organization
    category = models.CharField(max_length=100, null=True, blank=True)
    
    # For SEO and search optimization
    keywords = models.TextField(blank=True, null=True, 
                               help_text="Keywords for search optimization, comma-separated")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Product Families"
        indexes = [
            models.Index(fields=['manufacturer', 'model']),
            models.Index(fields=['product_type']),
        ]
        
    def __str__(self):
        return f"{self.name} ({self.sku})"
        
    @property
    def total_inventory(self):
        """Aggregate inventory across all products in this family"""
        from inventory.models import Inventory
        from django.db.models import Sum
        
        return Inventory.objects.filter(
            product__family=self
        ).aggregate(
            quantity=Sum('quantity'),
            available=Sum('available_quantity')
        )
        
    def get_products(self):
        """Return all products in this family"""
        return self.variants.all()  # Or self.products.all() if you rename
    
    def get_active_products(self):
        """Return only active products in this family"""
        # Assuming you have an is_active field on Product or similar
        return self.variants.filter(is_active=True)
