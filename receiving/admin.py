from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import ReceiptBatch, BatchItem
from inventory.models import InventoryReceipt


class BatchItemInline(admin.TabularInline):
    """Inline admin for BatchItems within a batch"""
    model = BatchItem
    fields = [
        'product', 'quantity', 'unit_cost', 
        'total_cost', 'requires_unit_qc', 
        'create_product_units', 'skip_inventory_receipt',
        'is_processed', 'inventory_receipt_link'
    ]
    readonly_fields = ['is_processed', 'total_cost', 'inventory_receipt_link']
    extra = 1
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('product', 'inventory_receipt')
    
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # Optimize product dropdown
        if db_field.name == 'product':
            kwargs['queryset'] = kwargs.get('queryset', db_field.remote_field.model.objects.all())
            kwargs['queryset'] = kwargs['queryset'].select_related()
            
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def inventory_receipt_link(self, obj):
        """Link to inventory receipt admin if one exists"""
        if obj.inventory_receipt:
            url = reverse('admin:inventory_inventoryreceipt_change', args=[obj.inventory_receipt.id])
            return format_html('<a href="{}">{}</a>', url, obj.inventory_receipt.id)
        return "-"
    inventory_receipt_link.short_description = "Inventory Receipt"


class ReceiptInline(admin.TabularInline):
    """Inline admin for receipts within a batch"""
    model = InventoryReceipt
    fields = [
        'product', 'quantity', 'unit_cost', 
        'total_cost', 'requires_unit_qc', 
        'create_product_units', 'is_processed'
    ]
    readonly_fields = ['is_processed', 'total_cost']
    extra = 1
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('product', 'location')
    
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # Make the location field read-only for existing receipts
        if db_field.name == 'location':
            kwargs['required'] = False
            
        # Optimize product dropdown
        if db_field.name == 'product':
            kwargs['queryset'] = kwargs.get('queryset', db_field.remote_field.model.objects.all())
            kwargs['queryset'] = kwargs['queryset'].select_related()
            
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(BatchItem)
class BatchItemAdmin(admin.ModelAdmin):
    """Admin for batch items"""
    list_display = [
        'id', 'batch_link', 'product_display', 'quantity', 
        'get_unit_cost', 'get_total_cost', 'skip_inventory_receipt',
        'is_processed', 'inventory_receipt_link', 'created_at'
    ]
    list_filter = [
        'skip_inventory_receipt', 'requires_unit_qc', 
        'create_product_units', 'created_at'
    ]
    search_fields = ['product__name', 'product__sku', 'batch__batch_code', 'notes']
    readonly_fields = [
        'id', 'is_processed', 'total_cost', 'inventory_receipt_link',
        'batch_link', 'created_at'
    ]
    
    fieldsets = [
        (None, {
            'fields': [
                'id',
                ('batch', 'batch_link'), 
                ('product', 'quantity'),
                ('unit_cost', 'total_cost'),
                'notes',
            ]
        }),
        ('Processing Options', {
            'fields': [
                'skip_inventory_receipt',
                ('requires_unit_qc', 'create_product_units'),
                ('is_processed', 'inventory_receipt_link'),
            ]
        }),
        ('System Information', {
            'fields': [
                'created_at',
            ],
            'classes': ['collapse']
        })
    ]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('product', 'batch', 'inventory_receipt')
    
    def product_display(self, obj):
        """Display product with SKU"""
        return f"{obj.product.sku} - {obj.product.name}"
    product_display.short_description = "Product"
    
    def get_unit_cost(self, obj):
        """Format unit cost with currency"""
        if obj.unit_cost:
            return f"{obj.batch.currency} {obj.unit_cost:.2f}"
        return "-"
    get_unit_cost.short_description = "Unit Cost"
    
    def get_total_cost(self, obj):
        """Format total cost with currency"""
        if obj.total_cost:
            return f"{obj.batch.currency} {obj.total_cost:.2f}"
        return "-"
    get_total_cost.short_description = "Total Cost"
    
    def batch_link(self, obj):
        """Link to batch admin"""
        if obj.batch:
            url = reverse('admin:receiving_receiptbatch_change', args=[obj.batch.id])
            return format_html('<a href="{}">{}</a>', url, obj.batch.batch_code)
        return "-"
    batch_link.short_description = "Batch"
    
    def inventory_receipt_link(self, obj):
        """Link to inventory receipt admin if one exists"""
        if obj.inventory_receipt:
            url = reverse('admin:inventory_inventoryreceipt_change', args=[obj.inventory_receipt.id])
            return format_html('<a href="{}">{}</a>', url, obj.inventory_receipt.id)
        return "-"
    inventory_receipt_link.short_description = "Inventory Receipt"
    
    def save_model(self, request, obj, form, change):
        """Handle saving a batch item, including creating inventory receipts"""
        creating = not obj.pk
        
        # Save the batch item first
        super().save_model(request, obj, form, change)
        
        # If creating a new batch item and not skipping inventory receipt
        if creating and not obj.skip_inventory_receipt and not obj.inventory_receipt:
            # Create inventory receipt
            batch = obj.batch
            
            receipt_data = {
                'product': obj.product,
                'quantity': obj.quantity,
                'location': batch.location,
                'unit_cost': obj.unit_cost,
                'requires_unit_qc': obj.requires_unit_qc,
                'create_product_units': obj.create_product_units,
                'is_processed': False,
                'reference': batch.reference,
                'batch_code': batch.batch_code,
                'batch': batch,
                'created_by': request.user,
                'notes': obj.notes
            }
            
            receipt = InventoryReceipt.objects.create(**receipt_data)
            
            # Link inventory receipt to the batch item
            obj.inventory_receipt = receipt
            obj.save(update_fields=['inventory_receipt'])
            
            # Update batch totals
            batch.calculate_totals()


@admin.register(ReceiptBatch)
class ReceiptBatchAdmin(admin.ModelAdmin):
    """Admin for receipt batches"""
    list_display = [
        'batch_code', 'reference', 'receipt_date', 'location', 
        'item_count', 'total_quantity', 'get_total_cost', 
        'status', 'created_by'
    ]
    list_filter = ['status', 'receipt_date', 'location', 'created_by']
    search_fields = ['reference', 'batch_code', 'notes']
    date_hierarchy = 'receipt_date'
    inlines = [BatchItemInline, ReceiptInline]  # Add BatchItemInline first
    readonly_fields = [
        'id', 'created_by', 'receipt_date', 'get_total_cost', 
        'item_count', 'total_quantity', 'completed_at', 'status_display'
    ]
    actions = ['process_selected_batches']
    
    fieldsets = [
        (None, {
            'fields': [
                ('reference', 'batch_code'),
                ('location', 'receipt_date'),
                ('status', 'status_display'),
                'notes',
            ]
        }),
        ('Shipping Information', {
            'fields': [
                ('shipping_carrier', 'shipping_tracking'),
            ]
        }),
        ('Cost Information', {
            'fields': [
                ('total_cost', 'currency'),
            ]
        }),
        ('Seller Information', {
            'fields': [
                'seller_info',
            ],
            'classes': ['collapse']
        }),
        ('System Information', {
            'fields': [
                ('created_by', 'id'),
                ('item_count', 'total_quantity'),
                'completed_at'
            ],
            'classes': ['collapse']
        })
    ]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('location', 'created_by')
    
    def get_total_cost(self, obj):
        """Format total cost with currency"""
        if obj.total_cost:
            return f"{obj.currency} {obj.total_cost:.2f}"
        return "-"
    get_total_cost.short_description = "Total Cost"
    
    def item_count(self, obj):
        """Get number of distinct items in batch"""
        return obj.items.count()  # Changed from receipts to items
    item_count.short_description = "Items"
    
    def total_quantity(self, obj):
        """Get total quantity of all items"""
        return obj.total_items
    total_quantity.short_description = "Total Quantity"
    
    def status_display(self, obj):
        """Format status with color"""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())
    status_display.short_description = "Status"
    
    def save_model(self, request, obj, form, change):
        """Set created_by to current user on creation"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        """Save inline items and handle creating inventory receipts"""
        instances = formset.save(commit=False)
        
        for instance in instances:
            if isinstance(instance, InventoryReceipt):
                # Set batch and defaults
                instance.batch = form.instance
                
                # Inherit location from batch if not set
                if not instance.location:
                    instance.location = form.instance.location
                
                # Set created_by
                if not instance.created_by:
                    instance.created_by = request.user
                
                # Save
                instance.save()
            elif isinstance(instance, BatchItem):
                # Save the batch item
                instance.batch = form.instance
                instance.save()
                
                # Create inventory receipt if needed
                if not instance.skip_inventory_receipt and not instance.inventory_receipt:
                    receipt_data = {
                        'product': instance.product,
                        'quantity': instance.quantity,
                        'location': form.instance.location,
                        'unit_cost': instance.unit_cost,
                        'requires_unit_qc': instance.requires_unit_qc,
                        'create_product_units': instance.create_product_units,
                        'is_processed': False,
                        'reference': form.instance.reference,
                        'batch_code': form.instance.batch_code,
                        'batch': form.instance,
                        'created_by': request.user,
                        'notes': instance.notes
                    }
                    
                    receipt = InventoryReceipt.objects.create(**receipt_data)
                    
                    # Link inventory receipt to the batch item
                    instance.inventory_receipt = receipt
                    instance.save(update_fields=['inventory_receipt'])
                
        # Handle deletions
        for obj in formset.deleted_objects:
            # If deleting a batch item with a receipt, delete the receipt too
            if isinstance(obj, BatchItem) and obj.inventory_receipt and not obj.inventory_receipt.is_processed:
                obj.inventory_receipt.delete()
            obj.delete()
        
        formset.save_m2m()
        
        # Update batch totals
        form.instance.calculate_totals()
        
    def process_selected_batches(self, request, queryset):
        """Admin action to process selected batches"""
        processed_count = 0
        for batch in queryset:
            if batch.process_batch():
                processed_count += 1
                
        if processed_count:
            self.message_user(request, f"Successfully processed {processed_count} batches.")
        else:
            self.message_user(request, "No batches were processed. They may already be complete.")
    process_selected_batches.short_description = "Process selected batches"
