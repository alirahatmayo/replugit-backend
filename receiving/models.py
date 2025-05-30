from django.db import models
import uuid
from django.utils import timezone
from django.conf import settings
import random
import string
from django.db.models import Sum

class ReceiptBatch(models.Model):
    """Master record for batch of received inventory items"""
    # id = models.AutoField(primary_key=True)
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="PO number or reference")
    receipt_date = models.DateTimeField(default=timezone.now)
    location = models.ForeignKey('inventory.Location', on_delete=models.CASCADE)
    batch_code = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # Shipping and logistics
    shipping_tracking = models.CharField(max_length=100, blank=True, null=True)
    shipping_carrier = models.CharField(max_length=100, blank=True, null=True)
    
    # Seller information
    seller_info = models.JSONField(null=True, blank=True)
    
    # Cost information
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Receipt Batch {self.batch_code or self.id} - {self.receipt_date}"
    
    class Meta:
        ordering = ['-receipt_date']
        verbose_name = "Receipt Batch"
        verbose_name_plural = "Receipt Batches"
        
    def save(self, *args, **kwargs):
        """Generate batch code if not provided"""
        if not self.batch_code:
            # Format: R-YYMMDD-XXXX (where XXXX is a random alphanumeric suffix)
            date_part = timezone.now().strftime('%y%m%d')
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            self.batch_code = f"R-{date_part}-{suffix}"
            
        super().save(*args, **kwargs)

    def _get_service(self):
        """
        Private method to get service class.
        This pattern allows for future dependency injection without changing the public API.
        """
        from .services import ReceivingBatchService
        return ReceivingBatchService

    def process_batch(self):
        """
        Process all unprocessed receipts in this batch.
        
        Returns:
            bool: True if any items were processed, False otherwise
        """
        return self._get_service().process_batch(self)

    def mark_completed(self):
        """Mark this batch as completed"""
        return self._get_service().mark_as_completed(self)
    
    def get_status_display_class(self):
        """Return Bootstrap class for status display"""
        status_classes = {
            'pending': 'secondary',
            'processing': 'primary',
            'completed': 'success',
            'cancelled': 'danger'
        }
        return status_classes.get(self.status, 'secondary')
    
    def can_be_processed(self):
        """Check if batch is eligible for processing"""
        return self.status in ['pending', 'processing'] and self.items.exists()
    
    def can_be_cancelled(self):
        """Check if batch can be cancelled"""
        return self.status != 'completed' and self.status != 'cancelled'
        
    def process_qc_required_items(self):
        """
        Create QC records for items that require quality control.
        This method is called during batch processing to separate QC workflow.
        """
        from quality_control.services import QualityControlService
        
        qc_records_created = 0
        for item in self.items.filter(requires_unit_qc=True):
            # Create QC record but don't create inventory receipt yet
            QualityControlService.create_qc_record_for_batch_item(item)
            qc_records_created += 1
            
        return qc_records_created

    def calculate_totals(self):
        """
        Calculate total cost and quantity from all batch items.
        
        Returns:
            dict: Dictionary with total_cost and total_items
        """
        return self._get_service().calculate_totals(self)

    @property
    def is_processed(self):
        """
        Check if the batch is fully processed.
        
        Returns:
            bool: True if the batch is processed, False otherwise
        """
        return self._get_service().is_batch_processed(self)
        
    @property
    def total_items(self):
        """Get total quantity of all items in this batch"""
        return self.items.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def unprocessed_items(self):
        """Get items that need processing"""
        return self._get_service().get_unprocessed_items(self)
        
    @property
    def processable_items(self):
        """Get items that can be processed immediately"""
        return self._get_service().get_processable_items(self)


class BatchItem(models.Model):
    """Record of a product family in a receipt batch"""
    DESTINATION_CHOICES = [
        ('inventory', 'Direct to Inventory'),
        ('qc', 'Quality Control'),
        ('pending', 'Pending Decision')
    ]
    
    batch = models.ForeignKey(ReceiptBatch, on_delete=models.CASCADE, related_name='items')
    
    # Use only product_family (renamed from parent_product for clarity)
    product_family = models.ForeignKey('products.ProductFamily', on_delete=models.CASCADE, 
                                      verbose_name="Product Family", null=True, blank=True)
    
    # Optional field to specify which variant to use (if known)
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='+',
                                         help_text="Preferred product variant (optional)")
    
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    # New field to track destination
    destination = models.CharField(
        max_length=20, 
        choices=DESTINATION_CHOICES, 
        default='pending',
        help_text="Where to send this item after receiving"
    )
    
    # Control flags
    skip_inventory_receipt = models.BooleanField(default=False)
    requires_unit_qc = models.BooleanField(default=False)
    create_product_units = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    inventory_receipt = models.OneToOneField('inventory.InventoryReceipt', on_delete=models.SET_NULL, 
                                           null=True, blank=True, related_name='from_batch_item')
    
    # Optional source tracking - which manifest this came from, if any
    source_type = models.CharField(max_length=50, blank=True, null=True, 
                                  help_text="Source system type (e.g., 'manifest')")
    source_id = models.CharField(max_length=100, blank=True, null=True,
                                help_text="ID in the source system")
    
    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'product_family'],
                name='unique_batch_family'
            )
        ]
    
    def __str__(self):
        # Check which type of product reference we have
        if self.product_family:
            product_text = self.product_family.sku
            variant_text = f" (via {self.preferred_variant.sku})" if hasattr(self, 'preferred_variant') and self.preferred_variant else ""
        elif self.product:
            product_text = self.product.sku
            variant_text = ""
        else:
            product_text = "Unknown Product"
            variant_text = ""
        
        batch_text = self.batch.batch_code if self.batch and self.batch.batch_code else f"Batch #{self.batch.id}" if self.batch else "No Batch"
        
        return f"{product_text}{variant_text} x {self.quantity} in {batch_text}"
    
    def save(self, *args, **kwargs):
        """Calculate total cost on save"""
        if self.unit_cost and self.quantity:
            self.total_cost = self.unit_cost * self.quantity
            
        # Validate that product belongs to product_family if specified
        if self.product and self.product_family:
            if self.product.family_id != self.product_family.id:
                raise ValueError("Preferred variant must belong to the specified product family")
            
        super().save(*args, **kwargs)
    
    @property
    def is_processed(self):
        """Check if this item has been processed"""
        if self.skip_inventory_receipt:
            return True
        return self.inventory_receipt and self.inventory_receipt.is_processed

