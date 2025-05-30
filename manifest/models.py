from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import uuid

class Manifest(models.Model):
    """Master record for an uploaded manifest file"""
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='manifests/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # Processing status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('mapping', 'Column Mapping'),
        ('validation', 'Validation'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Manifest type/format
    file_type = models.CharField(max_length=20, default='csv')
    has_header = models.BooleanField(default=True)
    
    # Mapping configuration (if using a saved template)
    template = models.ForeignKey('ManifestTemplate', on_delete=models.SET_NULL, 
                                null=True, blank=True, related_name='manifests')
    
    # Link to receiving batch (if created from this manifest)
    receipt_batch = models.ForeignKey('receiving.ReceiptBatch', 
                                     on_delete=models.SET_NULL, 
                                     null=True, blank=True,
                                     related_name='source_manifest')
    
    # Link to batch (used for bidirectional relationship with batches)
    # Updated to use ReceiptBatch instead of non-existent Batch
    batch = models.ForeignKey('receiving.ReceiptBatch',
                             on_delete=models.SET_NULL,
                             null=True, blank=True,
                             related_name='linked_manifests')
    
    # Metadata and statistics
    row_count = models.IntegerField(default=0)
    processed_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Common fields to store additional data
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="PO number or reference")
    notes = models.TextField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Manifest"
        verbose_name_plural = "Manifests"
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
        
    def mark_failed(self):
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

class ManifestTemplate(models.Model):
    """Saved column mapping configuration for reuse"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_default = models.BooleanField(default=False)
    
    # Default values to use when columns are missing
    default_values = models.JSONField(blank=True, null=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name

class ManifestColumnMapping(models.Model):
    """Maps a column from the manifest to a field in the system"""
    template = models.ForeignKey(ManifestTemplate, on_delete=models.CASCADE, related_name='column_mappings')
    source_column = models.CharField(max_length=100, help_text="Column name in source file")
    target_field = models.CharField(max_length=100, help_text="Field name in the system")
    
    # Transform options
    transform_function = models.CharField(max_length=100, blank=True, null=True, 
                                         help_text="Optional function to transform the value")
    is_required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=255, blank=True, null=True)
    
    # For grouping columns that should be processed together
    group_key = models.CharField(max_length=100, blank=True, null=True)
    
    # Order for processing (important for dependencies)
    processing_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['processing_order', 'source_column']
        unique_together = ['template', 'source_column']
    
    def __str__(self):
        return f"{self.source_column} → {self.target_field}"

class ManifestItem(models.Model):
    """Individual row from a manifest file"""
    manifest = models.ForeignKey(Manifest, on_delete=models.CASCADE, related_name='items')
    row_number = models.IntegerField()
    
    # Raw data from the manifest
    raw_data = models.JSONField()
      # Processing status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('mapped', 'Column Mapped'),
        ('validated', 'Validated'),
        ('error', 'Error'),
        ('processed', 'Processed')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
      # Family mapping reference - denormalized for performance
    # This references the group that provides the family mapping (same as 'group' when group has product_family)
    family_mapped_group = models.ForeignKey('ManifestGroup', on_delete=models.SET_NULL, 
                                           null=True, blank=True, db_index=True,
                                           related_name='family_mapped_items',
                                           help_text="Reference to group that provides family mapping for this item")
    
    # Mapped & transformed data ready for creating entities
    mapped_data = models.JSONField(blank=True, null=True)
    
    # Specific equipment fields (optimized for computer equipment based on example data)
    barcode = models.CharField(max_length=50, blank=True, null=True)
    serial = models.CharField(max_length=50, blank=True, null=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=255, blank=True, null=True)
    processor = models.CharField(max_length=255, blank=True, null=True)
    memory = models.CharField(max_length=50, blank=True, null=True)
    storage = models.CharField(max_length=100, blank=True, null=True)
    has_battery = models.BooleanField(default=False)
    battery = models.CharField(max_length=100, blank=True, null=True, help_text="Battery status or condition")
    condition_grade = models.CharField(max_length=10, blank=True, null=True)
    condition_notes = models.TextField(blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Link to batch item (if created from this manifest item)
    batch_item = models.ForeignKey('receiving.BatchItem', 
                                  on_delete=models.SET_NULL, 
                                  null=True, blank=True,
                                  related_name='manifest_items')
    
    # Error tracking
    error_message = models.TextField(blank=True, null=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Grouping reference
    group = models.ForeignKey('ManifestGroup', on_delete=models.SET_NULL, 
                             null=True, blank=True, related_name='items')
    
    class Meta:
        ordering = ['row_number']
        unique_together = ['manifest', 'row_number']
    
    def __str__(self):
        return f"Row {self.row_number}: {self.model or self.raw_data}"
    @property
    def is_mapped_to_family(self):
        """
        Returns True if this item is mapped to a product family through its group.
        Uses the denormalized family_mapped_group reference for performance.
        """
        return self.family_mapped_group is not None
    
    @property
    def effective_status(self):
        """
        Returns the effective status for frontend display.
        If the item is mapped to a family through its group, returns 'mapped',
        otherwise returns the actual status field.
        """
        if self.family_mapped_group is not None:
            return 'mapped'
        return self.status
    
    @property
    def mapped_family(self):
        """
        Returns the ProductFamily this item is mapped to through its group.
        """
        if self.family_mapped_group and self.family_mapped_group.product_family:
            return self.family_mapped_group.product_family
        return None
    
    def update_family_mapping_status(self):
        """
        Update the family_mapped_group field based on the current group relationship.
        Call this when the group or group's product_family changes.
        """
        new_mapped_group = None
        if self.group and self.group.product_family:
            new_mapped_group = self.group
        
        if self.family_mapped_group != new_mapped_group:
            self.family_mapped_group = new_mapped_group
            self.save(update_fields=['family_mapped_group'])
            return True
        return False

class ManifestGroup(models.Model):
    """
    Grouping of manifest items by similarity (e.g., same model, processor, memory)
    Used to consolidate similar items into a single batch item with quantity
    
    A ManifestGroup is uniquely identified by manufacturer, model, and product-type dependent attributes.
    These groups link directly to a single ProductFamily.
    """
    manifest = models.ForeignKey(Manifest, on_delete=models.CASCADE, related_name='groups')
    group_key = models.CharField(max_length=255, db_index=True, help_text="Hash of grouped fields")
    quantity = models.IntegerField(default=0)
    
    # Core identifying fields - always explicit
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=255, blank=True, null=True)
    
    # Direct single relationship to product family
    product_family = models.ForeignKey('products.ProductFamily', 
                                      on_delete=models.SET_NULL, 
                                      null=True, blank=True,
                                      related_name='manifest_groups')
    
    # Dynamic attributes stored as JSON - varies by product family type
    metadata = models.JSONField(default=dict, blank=True, 
                              help_text="Product-specific attributes (processor, memory, etc.)")
    
    # Link to batch item (if created from this manifest group)
    batch_item = models.OneToOneField('receiving.BatchItem', 
                                     on_delete=models.SET_NULL, 
                                     null=True, blank=True,
                                     related_name='manifest_group')
    
    class Meta:
        ordering = ['manifest', '-quantity']
        unique_together = ['manifest', 'group_key']
        indexes = [
            models.Index(fields=['manufacturer', 'model'], name='mg_mfg_model_idx'),
            models.Index(fields=['product_family'], name='mg_family_idx'),
            models.Index(fields=['quantity'], name='mg_quantity_idx'),
        ]
    
    def __str__(self):
        return f"{self.manufacturer} {self.model} x {self.quantity}"
        
    def generate_group_key(self):
        """
        Generate a deterministic hash based on manufacturer, model and 
        product-family-specific attributes from metadata.
        
        Returns:
            str: A hash representing the unique grouping criteria
        """
        import hashlib
        import json
        
        # Base key components - always include these
        key_components = {
            'manufacturer': self.manufacturer or '',
            'model': self.model or ''
        }
        
        # Get product family type if available
        family_type = None
        if self.product_family:
            family_type = getattr(self.product_family, 'product_type', '').lower()
        
        # Add product family type-specific fields from metadata
        metadata = self.metadata or {}
        
        if family_type == 'laptop':
            for field in ['processor', 'memory', 'storage']:
                if field in metadata:
                    key_components[field] = metadata.get(field, '')
                    
        elif family_type == 'desktop':
            for field in ['processor', 'memory']:
                if field in metadata:
                    key_components[field] = metadata.get(field, '')
                    
        elif family_type == 'monitor':
            for field in ['screen_size', 'resolution']:
                if field in metadata:
                    key_components[field] = metadata.get(field, '')
        
        # Always include condition_grade if available
        if 'condition_grade' in metadata:
            key_components['condition_grade'] = metadata.get('condition_grade', '')
            
        # Convert to a stable string representation and hash
        key_str = json.dumps(key_components, sort_keys=True)
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()
        
    def save(self, *args, **kwargs):
        # Generate the group_key if not set
        if not self.group_key:
            self.group_key = self.generate_group_key()
            
        super().save(*args, **kwargs)

    def get_metadata(self, key, default=None):
        """
        Helper method to get a value from the metadata dictionary
        
        Args:
            key (str): The key to look up in the metadata
            default: The default value to return if key is not found
            
        Returns:
            The value for the key, or default if not found
        """
        if not self.metadata:
            return default
            
        return self.metadata.get(key, default)
        
    def set_metadata(self, key, value):
        """
        Helper method to set a value in the metadata dictionary
        
        Args:
            key (str): The key to set in the metadata
            value: The value to set
            
        Note: This method does not save the model after updating
        """
        if self.metadata is None:
            self.metadata = {}
            
        self.metadata[key] = value


# Signal handlers for keeping ManifestItem.is_family_mapped in sync
@receiver(pre_save, sender='manifest.ManifestGroup')
def manifest_group_pre_save(sender, instance, **kwargs):
    """Track changes to product_family field before saving"""
    if instance.pk:
        try:
            old_instance = ManifestGroup.objects.get(pk=instance.pk)
            instance._old_product_family = old_instance.product_family
        except ManifestGroup.DoesNotExist:
            instance._old_product_family = None
    else:
        instance._old_product_family = None

@receiver(post_save, sender='manifest.ManifestGroup')
def manifest_group_post_save(sender, instance, **kwargs):
    """Update ManifestItem.is_family_mapped when group's product_family changes"""
    old_family = getattr(instance, '_old_product_family', None)
    new_family = instance.product_family
    
    # Only update if the product_family actually changed
    if old_family != new_family:
        # Update all items in this group
        for item in instance.items.all():
            item.update_family_mapping_status()

@receiver(post_save, sender='manifest.ManifestItem')
def manifest_item_group_changed(sender, instance, **kwargs):
    """Update is_family_mapped when item's group changes"""
    # This will be called when an item is assigned to or removed from a group
    instance.update_family_mapping_status()

