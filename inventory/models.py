from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid
from receiving.models import BatchItem
from django.db import transaction


# Create your models here.

class Location(models.Model):
    """Physical inventory location/warehouse"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    default_location = models.BooleanField(default=False, help_text="Default location for new items")
    
    def __str__(self):
        return self.name
        
    class Meta:
        ordering = ['name']

class Inventory(models.Model):
    """Core inventory tracking model"""
    STATUS_CHOICES = [
        ('IN_STOCK', 'In Stock'),
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('BACKORDER', 'Backordered'),
        ('DISCONTINUED', 'Discontinued')
    ]
    
    # Relationships
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='inventory_records')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='inventories', null=True)
    
    # Stock information
    quantity = models.IntegerField(default=0)
    available_quantity = models.IntegerField(default=0)  # Accounts for reservations
    reserved_quantity = models.IntegerField(default=0)  # For pending orders
    
    # Platform-specific
    platform = models.CharField(max_length=50, null=True, blank=True)
    platform_sku = models.CharField(max_length=100, null=True, blank=True)
    
    # Settings
    reorder_point = models.IntegerField(default=5, help_text="Quantity at which to reorder")
    reorder_quantity = models.IntegerField(default=10, help_text="Suggested reorder amount")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OUT_OF_STOCK')
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    last_count = models.DateTimeField(null=True, blank=True, help_text="Last physical count date")
    
    class Meta:
        verbose_name_plural = 'Inventories'
        unique_together = [['product', 'location', 'platform']]
        
    def __str__(self):
        platform_str = f" ({self.platform})" if self.platform else ""
        return f"{self.product.sku}{platform_str}: {self.quantity} @ {self.location.name}"
    
    def save(self, *args, **kwargs):
        # Calculate available quantity
        self.available_quantity = max(0, self.quantity - self.reserved_quantity)
        
        # Update status
        self.update_status()
        
        # Save the model
        super().save(*args, **kwargs)
    
    def update_status(self):
        """Update status based on quantity"""
        if self.quantity <= 0:
            self.status = 'OUT_OF_STOCK'
        elif self.quantity <= self.reorder_point:
            self.status = 'LOW_STOCK'
        else:
            self.status = 'IN_STOCK'
    
    def adjust_quantity(self, adjustment, reason="MANUAL", reference=None, notes=None, user=None):
        """
        Adjust inventory quantity and create history record
        
        Args:
            adjustment: Amount to adjust (positive or negative)
            reason: Reason for adjustment
            reference: Reference document (order ID, etc)
            notes: Additional notes
            user: User making adjustment
            
        Returns:
            InventoryHistory record
        """
        previous_quantity = self.quantity
        self.quantity += adjustment
        self.save()
        
        # Create history record
        history = InventoryHistory.objects.create(
            inventory=self,
            previous_quantity=previous_quantity,
            new_quantity=self.quantity,
            change=adjustment,
            reason=reason,
            reference=reference,
            notes=notes,
            adjusted_by=user
        )
        
        return history

class InventoryHistory(models.Model):
    """Track inventory changes over time"""
    REASON_CHOICES = [
        ('MANUAL', 'Manual Adjustment'),
        ('SALE', 'Sale'),
        ('PURCHASE', 'Purchase/Restock'),
        ('RETURN', 'Customer Return'),
        ('SYNC', 'Platform Sync'),
        ('TRANSFER', 'Location Transfer'),
        ('COUNT', 'Physical Count'),
        ('DAMAGED', 'Damaged/Write-off')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='history')
    
    # Change information
    previous_quantity = models.IntegerField()
    new_quantity = models.IntegerField()
    change = models.IntegerField()  # Can be positive or negative
    
    # Metadata
    timestamp = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    reference = models.CharField(max_length=100, null=True, blank=True)  # Order ID, etc.
    notes = models.TextField(null=True, blank=True)
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, 
                                  on_delete=models.SET_NULL, related_name='inventory_adjustments')
    
    class Meta:
        verbose_name_plural = 'Inventory histories'
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.inventory.product.sku}: {'+' if self.change >= 0 else ''}{self.change} @ {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class StockAlert(models.Model):
    """Configure inventory alerts"""
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='stock_alerts')
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.CASCADE)
    
    # Alert thresholds
    low_threshold = models.IntegerField(default=5)
    critical_threshold = models.IntegerField(default=2)
    
    # Notification settings
    notify_emails = models.TextField(null=True, blank=True, 
                                   help_text="Comma-separated list of emails to notify")
    
    # Alert status
    is_active = models.BooleanField(default=True)
    last_notified = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['product', 'location']]
    
    def __str__(self):
        location_name = self.location.name if self.location else "All Locations"
        return f"Alert: {self.product.sku} @ {location_name}"

class InventoryAdjustment(models.Model):
    """Pending inventory adjustments (for approval workflow)"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='adjustments')
    
    # Adjustment details
    quantity_change = models.IntegerField(help_text="Can be positive or negative")
    reason = models.CharField(max_length=20, choices=InventoryHistory.REASON_CHOICES)
    reference = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    # Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                                 related_name='created_adjustments')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, 
                                  on_delete=models.SET_NULL, related_name='approved_adjustments')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Adjustment {self.id}: {'+' if self.quantity_change >= 0 else ''}{self.quantity_change} ({self.status})"
    
    def approve(self, user):
        """Approve and execute adjustment"""
        if self.status != 'PENDING':
            return False
            
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()
        
        # Apply the adjustment
        self.inventory.adjust_quantity(
            adjustment=self.quantity_change,
            reason=self.reason,
            reference=self.reference,
            notes=self.notes,
            user=user
        )
        
        self.status = 'COMPLETED'
        self.save()
        
        return True
    
    def reject(self, user, rejection_reason=None):
        """Reject adjustment"""
        if self.status != 'PENDING':
            return False
            
        self.status = 'REJECTED'
        self.approved_by = user
        self.approved_at = timezone.now()
        
        if rejection_reason:
            self.notes = f"{self.notes}\n\nREJECTED: {rejection_reason}"
            
        self.save()
        return True

class InventoryReceipt(models.Model):
    """Record of inventory received, with ability to process and create units"""
    # Always link to product family
    product_family = models.ForeignKey('products.ProductFamily', on_delete=models.CASCADE, null=True, blank=True)
    
    # Optional link to specific variant used
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, 
                                        null=True, blank=True,
                                        help_text="Specific variant allocated for this receipt")
    
    quantity = models.PositiveIntegerField()
    location = models.ForeignKey('Location', on_delete=models.CASCADE, null=True, blank=True)
      # Receipt metadata
    receipt_date = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="PO number or reference")
    notes = models.TextField(blank=True, null=True)
    batch_code = models.CharField(max_length=50, blank=True, null=True, help_text="Optional batch identifier")
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

    @classmethod
    def get_or_create_system_user(cls):
        """Get or create a system user for automatic assignments"""
        from django.contrib.auth.models import User
        return User.objects.get_or_create(
            username='system',
            defaults={
                'email': 'system@replugit.com',
                'first_name': 'System',
                'last_name': 'User',
                'is_active': True
            }
        )[0]
    
    # Seller information stored as JSON
    seller_info = models.JSONField(
        null=True, 
        blank=True,
        help_text="Detailed information about the seller/supplier"
    )
    
    # Cost information
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    
    # Shipping and logistics
    shipping_tracking = models.CharField(max_length=100, blank=True, null=True)
    shipping_carrier = models.CharField(max_length=100, blank=True, null=True)
    
    requires_unit_qc = models.BooleanField(default=False,help_text="Whether each unit requires individual QC")
    create_product_units = models.BooleanField(default=True, help_text="Whether to create individual product units for this receipt")
    
    # New field to link to batch
    batch = models.ForeignKey('receiving.ReceiptBatch', on_delete=models.SET_NULL, null=True, blank=True, related_name='receipts')
    is_processed = models.BooleanField(default=False, help_text="Whether this receipt has been processed")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-receipt_date']
        verbose_name = "Inventory Receipt"
        verbose_name_plural = "Inventory Receipts"
        # Add constraint to ensure product_family is set
        constraints = [
            models.CheckConstraint(
                check=models.Q(product_family__isnull=False) | models.Q(product__isnull=False),
                name='receipt_has_product_or_family'
            ),
            models.CheckConstraint(
                check=~(models.Q(product_family__isnull=True) & models.Q(product__isnull=True)),
                name='receipt_must_have_product_reference'
            )
        ]

    @property
    def quality_control(self):
        """
        Get the associated quality control record if it exists
        """
        from quality_control.models import QualityControl
        try:
            return QualityControl.objects.get(inventory_receipt=self)
        except QualityControl.DoesNotExist:
            return None
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Inherit batch fields if this receipt belongs to a batch
        if self.batch:
            self.inherit_batch_fields()
        
        # If receipt has batch but no location, use batch location
        if self.batch and not self.location:
            self.location = self.batch.location
        
        # If still no location, try to find default location
        if not self.location:
            try:
                self.location = Location.objects.filter(default_location=True).first()
            except:
                pass  # No default location found
        
        # Save the receipt first
        super().save(*args, **kwargs)
        
        # Only auto-process for new standalone receipts (not batch)
        if is_new and not self.batch and not self.is_processed:
            self.process_receipt()        # Only generate units for new receipts and if allowed
        product_updated = False
        if is_new and self.should_create_product_units():
            original_product = self.product
            
            # Generate units - this may resolve the product via get_or_create_family_product()
            units = self.generate_product_units()
            
            # Check if product was updated during unit generation
            if self.product != original_product:
                product_updated = True
            
            # Update inventory levels - only if we have a resolved product and units were created
            if self.product and len(units) > 0:
                inventory, created = Inventory.objects.get_or_create(
                    product=self.product,
                    location=self.location,
                    defaults={'quantity': 0}  # Start with 0, then add quantity
                )
                
                if not created:
                    inventory.quantity += self.quantity
                else:
                    inventory.quantity = self.quantity
                inventory.save()
        
        # For new receipts that don't create units but still need inventory tracking
        elif is_new and self.product:
            inventory, created = Inventory.objects.get_or_create(
                product=self.product,
                location=self.location,
                defaults={'quantity': 0}
            )
            
            if not created:
                inventory.quantity += self.quantity
            else:
                inventory.quantity = self.quantity
            inventory.save()
        
        # Save the receipt again if product was updated during generation
        if product_updated:
            super().save(update_fields=['product'])
    
    def get_or_create_family_product(self):
        """
        Get or create a default product for the product family.
        
        This method handles the common scenario where we have a product family
        but no specific product variant. It will:
        1. Try to find an existing primary product in the family
        2. Fall back to the first available product in the family
        3. Create a new default product if none exist
        
        Returns:
            Product: The product to use for inventory operations
            
        Raises:
            ValueError: If neither product nor product_family is specified
        """
        # If we already have a specific product, use it
        if self.product:
            return self.product
            
        # Must have at least a product family
        if not self.product_family:
            raise ValueError("Either product or product_family must be specified")
        
        # Try to find existing products in the family
        # Note: Removed is_active filter since Product model doesn't have this field
        family_products = self.product_family.products.all()
        
        # Prefer primary listing, otherwise use the first available product
        target_product = (
            family_products.filter(is_primary_listing=True).first() or 
            family_products.first()
        )
          # If no products exist in the family, create a default one
        if not target_product:
            from products.models import Product
            
            # Generate a unique SKU for the default product
            default_sku = (
                f"{self.product_family.sku}-DEF" 
                if hasattr(self.product_family, 'sku') and self.product_family.sku
                else f"DEF-{self.product_family.id}"
            )
            
            # Create the default product
            target_product = Product.objects.create(
                name=f"{self.product_family.name} (Default)",
                sku=default_sku,
                family=self.product_family,
                is_primary_listing=True,
                # Note: Removed is_active=True since Product model doesn't have this field
            )
            
            # Log the creation for audit purposes
            creation_note = f"Created default product {target_product.sku} for family {self.product_family.name}."
            self.notes = f"{self.notes or ''}. {creation_note}"
            
            print(f"✓ Created default product: {target_product.sku} for family: {self.product_family.name}")
        
        # Always update this receipt to reference the resolved product
        # This ensures future operations use the same product
        if target_product != self.product:
            self.product = target_product
            print(f"✓ Resolved product {target_product.sku} for receipt {self.id}")
        
        return target_product

    def _get_safe_batch_code(self):
        """
        Generate a safe batch_code that fits within the 50-character limit for ProductUnit.
        Priority order:
        1. Use self.batch_code if set and within limit
        2. Use truncated reference if available  
        3. Generate default BATCH-{id} format
        """
        # First priority: use existing batch_code if it fits
        if self.batch_code:
            if len(self.batch_code) <= 50:
                return self.batch_code
            else:
                # Truncate long batch_code
                return self.batch_code[:47] + "..."
        
        # Second priority: use reference (truncated if needed)
        if self.reference:
            if len(self.reference) <= 50:
                return self.reference
            else:
                return self.reference[:47] + "..."
        
        # Fallback: generate based on receipt ID
        return f"BATCH-{self.id}"

    @transaction.atomic
    def generate_product_units(self):
        """
        Generate individual product units for this receipt if allowed.
        
        UPDATED: Now uses get_or_create_family_product() to handle
        the case where no products exist in a family.
        """
        from products.models import ProductUnit
        
        # Early return if units shouldn't be created
        if not self.create_product_units:
            return []
        
        print(f"🔧 Generating product units for receipt {self.id}")
        
        # UPDATED: Use the shared method instead of manual product resolution
        # This ensures consistent behavior with inventory updates
        try:
            target_product = self.get_or_create_family_product()
            print(f"✓ Using product: {target_product.sku} for unit generation")
        except Exception as e:
            error_msg = f"Cannot create units for receipt {self.id}: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        # Continue with the rest of your existing unit creation logic
        units_created = []
        qc_record = None
        
        # Try to get QC record through related name
        if hasattr(self, 'quality_control'):
            try:
                qc_record = self.quality_control
            except Exception:
                pass
    
        for i in range(self.quantity):
            # Prepare QC metadata
            qc_metadata = None
            if qc_record:
                qc_metadata = {
                    "qc_id": str(qc_record.id),
                    "batch_code": qc_record.batch_code,
                    "inspection_date": qc_record.inspected_at.isoformat() if qc_record.inspected_at else None,
                    "requires_unit_qc": self.requires_unit_qc
                }
            
            # Set status based on whether it requires unit QC
            status = "pending_qc" if self.requires_unit_qc else "in_stock"
              # Create location details as a JSON object
            location_details = {}
            if hasattr(self.location, 'default_shelf'):
                location_details['shelf'] = self.location.default_shelf
            if hasattr(self.location, 'default_zone'):
                location_details['zone'] = self.location.default_zone
            
            unit = ProductUnit.objects.create(
                product=target_product,  # UPDATED: Use target_product instead of self.product
                status=status,
                location=self.location,
                location_details=location_details,
                batch_code=self._get_safe_batch_code(),
                metadata={
                    "receipt_id": str(self.id),
                    "receipt_date": self.receipt_date.isoformat(),
                    "qc": qc_metadata
                }
            )
            units_created.append(unit)
    
        print(f"✅ Successfully created {len(units_created)} product units")
        return units_created

    def should_create_product_units(self):
        """Determine if product units should be created for this receipt"""
        # Basic check - does the flag allow it?
        if not self.create_product_units:
            return False
            
        # Is the product serialized?
        if hasattr(self.product, 'is_serialized') and not self.product.is_serialized:
            return False
            
        # Are we tracking at unit level?
        from django.conf import settings
        track_units = getattr(settings, 'INVENTORY_TRACK_UNITS', True)
        
        # Check subscription level if applicable
        if hasattr(settings, 'SUBSCRIPTION_ALLOWS_UNIT_TRACKING'):
            return settings.SUBSCRIPTION_ALLOWS_UNIT_TRACKING
            
        return track_units
        
    def get_seller_name(self):
        """Extract seller name from seller_info JSON"""
        if not self.seller_info:
            return None
        
        return self.seller_info.get('name', self.seller_info.get('company_name', None))
    
    def process_receipt(self):
        """Process this receipt by updating inventory and optionally creating units"""
        if self.is_processed:
            return False
            
        # Update inventory
        self._update_inventory()
        
        # Create product units if needed
        if self.create_product_units:
            self.generate_product_units()
        
        # Mark as processed
        self.is_processed = True
        self.processed_at = timezone.now()
        self.save(update_fields=['is_processed', 'processed_at'])
        
        return True
    
    def _update_inventory(self):
        """Update inventory levels for this product or product family"""
        # Case 1: Direct product specified - use it directly
        if self.product:
            inventory, created = Inventory.objects.get_or_create(
                product=self.product,
                location=self.location,
                defaults={'quantity': 0, 'available_quantity': 0}
            )
            
            # Update quantity
            inventory.quantity += self.quantity
            inventory.available_quantity += self.quantity
            inventory.save()
            
        # Case 2: Product family specified - find default product
        elif self.product_family:
            self._handle_family_inventory()
            
        # Should never happen due to constraint
        else:
            raise ValueError("Either product or product_family must be specified")
    
    def _handle_family_inventory(self):
        """Find and use the default product from family"""
        family_products = self.product_family.products.filter(is_active=True)
        
        # Get default product (primary listing or first active product)
        target_product = family_products.filter(is_primary_listing=True).first() or family_products.first()
                
        if not target_product:
            # No products in family - create a placeholder
            from products.models import Product
            target_product = Product.objects.create(
                name=f"{self.product_family.name} (Default)",
                sku=f"{self.product_family.sku}-DEF",
                family=self.product_family,
                is_primary_listing=True,
                is_active=True
            )
            # Log this creation
            self.notes = f"{self.notes or ''}. Created placeholder product {target_product.sku} for family."
            self.save(update_fields=['notes'])
        
        # Update inventory for the selected product
        inventory, created = Inventory.objects.get_or_create(
            product=target_product,
            location=self.location,
            defaults={'quantity': 0, 'available_quantity': 0}
        )
        
        inventory.quantity += self.quantity
        inventory.available_quantity += self.quantity
        inventory.save()
        
        # Store which product was selected
        self.product = target_product
        self.notes = f"{self.notes or ''}. Inventory assigned to {target_product.sku}."
        self.save(update_fields=['notes', 'product'])
    
    def inherit_batch_fields(self):
        """Inherit fields from batch to avoid duplication"""
        if not self.batch:
            return False
              # Copy fields from batch to receipt if not set
        changed = False
        
        if not self.reference and self.batch.reference:
            self.reference = self.batch.reference
            changed = True
            
        if not self.batch_code and self.batch.batch_code:
            # Truncate inherited batch_code to fit field constraints
            self.batch_code = self.batch.batch_code[:50] if len(self.batch.batch_code) > 50 else self.batch.batch_code
            changed = True
            
        if not self.shipping_tracking and self.batch.shipping_tracking:
            self.shipping_tracking = self.batch.shipping_tracking
            changed = True
            
        if not self.shipping_carrier and self.batch.shipping_carrier:
            self.shipping_carrier = self.batch.shipping_carrier
            changed = True
            
        if not self.seller_info and self.batch.seller_info:
            self.seller_info = self.batch.seller_info
            changed = True
            
        if not self.notes and self.batch.notes:
            self.notes = self.batch.notes
            changed = True
            
        if not self.currency and self.batch.currency:
            self.currency = self.batch.currency
            changed = True
            
        # Always inherit location from batch
        if self.batch.location:
            self.location = self.batch.location
            changed = True
            
        return changed

    def get_batch_item(self):
        """Get the associated batch item if one exists"""
        try:
            # Using the related_name from BatchItem's inventory_receipt field
            return BatchItem.objects.get(inventory_receipt=self)
        except BatchItem.DoesNotExist:
            return None

    def __str__(self):
        if self.product:
            product_name = self.product.name
        elif self.product_family:
            product_name = f"{self.product_family.name} (Family)"
        else:
            product_name = "Unknown Product"
        
        return f"{product_name} - {self.quantity} units - {self.receipt_date.strftime('%Y-%m-%d')}"

class ProductUnitReceipt(models.Model):
    """Links product units to their receipt record"""
    product_unit = models.ForeignKey('products.ProductUnit', on_delete=models.CASCADE)
    receipt = models.ForeignKey(InventoryReceipt, on_delete=models.CASCADE, related_name='unit_entries')
    sequence = models.PositiveIntegerField(help_text="Sequence number within this receipt")
    
    class Meta:
        unique_together = ('receipt', 'sequence')
