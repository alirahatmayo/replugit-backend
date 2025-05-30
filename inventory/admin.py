from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Sum, F, Q
from django.contrib import messages  # Add this import

from .models import Location, Inventory, InventoryHistory, StockAlert, InventoryAdjustment, InventoryReceipt

class InventoryHistoryInline(admin.TabularInline):
    model = InventoryHistory
    extra = 0
    readonly_fields = ('timestamp', 'previous_quantity', 'new_quantity', 
                      'change', 'reason', 'reference', 'adjusted_by')
    can_delete = False
    max_num = 10  # Limit to 10 most recent
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('-timestamp')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'address', 'is_active', 'total_items', 'total_quantity')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'address')
    
    def total_items(self, obj):
        return obj.inventories.count()
    
    def total_quantity(self, obj):
        return obj.inventories.aggregate(Sum('quantity'))['quantity__sum'] or 0

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('product_sku', 'product_name', 'location', 'quantity', 
                   'available_quantity', 'reserved_quantity', 'status', 'platform', 'updated_at')
    list_filter = ('status', 'location', 'platform')
    search_fields = ('product__sku', 'product__name', 'platform_sku')
    readonly_fields = ('created_at', 'updated_at', 'last_sync')
    inlines = [InventoryHistoryInline]
    
    # FIX: Ensure this is a list of string action names, not methods
    action_list = ['update_status', 'set_zero_inventory']  # Renamed from "actions" to avoid conflict
    actions = action_list  # Assign the list to actions
    
    fieldsets = (
        ('Product Information', {
            'fields': ('product', 'platform', 'platform_sku')
        }),
        ('Inventory Details', {
            'fields': ('location', 'quantity', 'reserved_quantity', 'available_quantity', 'status')
        }),
        ('Settings', {
            'fields': ('reorder_point', 'reorder_quantity')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_sync', 'last_count'),
            'classes': ('collapse',)
        }),
    )
    
    def product_sku(self, obj):
        return obj.product.sku
    
    def product_name(self, obj):
        return obj.product.name
    
    def update_status(self, request, queryset):
        for inventory in queryset:
            inventory.update_status()
            inventory.save()
        self.message_user(request, f"Updated status for {queryset.count()} inventory items")
    
    def set_zero_inventory(self, request, queryset):
        for inventory in queryset:
            inventory.adjust_quantity(
                -inventory.quantity,
                reason="MANUAL",
                notes="Set to zero via admin",
                user=request.user
            )
        self.message_user(request, f"Set {queryset.count()} inventory items to zero")
    
    update_status.short_description = "Update inventory status"
    set_zero_inventory.short_description = "Set to zero inventory"

@admin.register(InventoryHistory)
class InventoryHistoryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'inventory_product', 'inventory_location', 
                   'previous_quantity', 'new_quantity', 'change', 'reason', 'reference', 'adjusted_by')
    list_filter = ('reason', 'inventory__location', 'timestamp')
    search_fields = ('inventory__product__sku', 'reference', 'notes')
    date_hierarchy = 'timestamp'
    readonly_fields = ('inventory', 'previous_quantity', 'new_quantity', 'change', 'timestamp')
    
    fieldsets = (
        ('Inventory Reference', {
            'fields': ('inventory',)
        }),
        ('Change Information', {
            'fields': ('previous_quantity', 'new_quantity', 'change', 'reason')
        }),
        ('Details', {
            'fields': ('reference', 'notes', 'adjusted_by', 'timestamp')
        }),
    )
    
    def inventory_product(self, obj):
        return obj.inventory.product.sku
    
    def inventory_location(self, obj):
        return obj.inventory.location.name

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('product', 'location', 'low_threshold', 'critical_threshold', 
                   'current_stock', 'status', 'is_active')
    list_filter = ('is_active', 'location')
    search_fields = ('product__sku', 'product__name')
    
    def current_stock(self, obj):
        if obj.location:
            inventory = Inventory.objects.filter(product=obj.product, location=obj.location).first()
        else:
            inventory = Inventory.objects.filter(product=obj.product).first()
            
        if inventory:
            return inventory.quantity
        return "N/A"
    
    def status(self, obj):
        stock = self.current_stock(obj)
        if stock == "N/A":
            return "Unknown"
        
        if stock <= obj.critical_threshold:
            return format_html('<span style="color:red;font-weight:bold">CRITICAL</span>')
        elif stock <= obj.low_threshold:
            return format_html('<span style="color:orange;font-weight:bold">LOW</span>')
        else:
            return format_html('<span style="color:green">OK</span>')

@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'inventory_product', 'inventory_location', 'quantity_change',
                   'reason', 'status', 'created_by', 'created_at', 'show_actions')
    list_filter = ('status', 'reason', 'inventory__location', 'created_at')
    search_fields = ('inventory__product__sku', 'reference', 'notes')
    readonly_fields = ('created_at', 'created_by', 'approved_by', 'approved_at')
    
    fieldsets = (
        ('Inventory Reference', {
            'fields': ('inventory',)
        }),
        ('Adjustment Details', {
            'fields': ('quantity_change', 'reason', 'reference', 'notes')
        }),
        ('Workflow', {
            'fields': ('status', 'created_by', 'created_at', 'approved_by', 'approved_at')
        }),
    )
    
    def inventory_product(self, obj):
        return obj.inventory.product.sku
    
    def inventory_location(self, obj):
        return obj.inventory.location.name
    
    # Renamed "actions" method to "show_actions" to avoid conflict with Django's actions list
    def show_actions(self, obj):
        if obj.status == 'PENDING':
            approve_url = reverse('admin:approve_adjustment', args=[obj.pk])
            reject_url = reverse('admin:reject_adjustment', args=[obj.pk])
            
            return format_html(
                '<a class="button" href="{}">Approve</a>&nbsp;'
                '<a class="button" href="{}">Reject</a>',
                approve_url, reject_url
            )
        return "-"
    
    show_actions.short_description = "Actions"  # Set column header
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:pk>/approve/',
                self.admin_site.admin_view(self.approve_adjustment),
                name='approve_adjustment',
            ),
            path(
                '<uuid:pk>/reject/',
                self.admin_site.admin_view(self.reject_adjustment),
                name='reject_adjustment',
            ),
        ]
        return custom_urls + urls
    
    def approve_adjustment(self, request, pk):
        from django.contrib import messages
        from django.shortcuts import redirect
        
        adjustment = self.get_object(request, pk)
        
        if adjustment.approve(request.user):
            messages.success(request, f"Adjustment {pk} approved and applied")
        else:
            messages.error(request, f"Could not approve adjustment {pk}")
            
        return redirect('admin:inventory_inventoryadjustment_changelist')
    
    def reject_adjustment(self, request, pk):
        from django.contrib import messages
        from django.shortcuts import redirect
        
        adjustment = self.get_object(request, pk)
        
        if adjustment.reject(request.user):
            messages.warning(request, f"Adjustment {pk} rejected")
        else:
            messages.error(request, f"Could not reject adjustment {pk}")
            
        return redirect('admin:inventory_inventoryadjustment_changelist')

@admin.register(InventoryReceipt)
class InventoryReceiptAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_display', 'quantity', 'location', 'receipt_date', 'is_processed')  
    list_filter = ('location', 'receipt_date', 'is_processed') 
    search_fields = ('id', 'product__name', 'product__sku', 'product_family__name', 'product_family__sku')  
    readonly_fields = ('receipt_date', 'is_processed')
    
    fieldsets = (
        (None, {
            'fields': (('product', 'product_family'), 'quantity', 'location', 'unit_cost') 
        }),
        ('Unit Tracking', {
            'fields': ('create_product_units', 'requires_unit_qc'),
            'classes': ('collapse',),
        }),
        ('Receipt Details', {
            'fields': ('receipt_date', 'batch_code', 'reference', 'notes'),
            'classes': ('collapse',),
        }),
        ('Processing', {
            'fields': ('is_processed',),  # Note the comma!
            'classes': ('collapse',),
        }),
    )
    
    actions = ['generate_units_for_receipts', 'process_receipts']
    
    def product_display(self, obj):
        """Display either product or product_family"""
        if obj.product:
            return f"{obj.product.name} ({obj.product.sku})"
        elif obj.product_family:
            return f"{obj.product_family.name} ({obj.product_family.sku}) [Family]"
        return "No product"
    product_display.short_description = 'Product'
    
    @admin.action(description="Generate product units for selected receipts")
    def generate_units_for_receipts(self, request, queryset):
        """Generate product units for selected receipts"""
        total_units = 0
        receipts_processed = 0
        
        for receipt in queryset:
            if not receipt.should_create_product_units():
                continue
                
            units = receipt.generate_product_units()
            total_units += len(units)
            receipts_processed += 1
            
        self.message_user(
            request,
            f"Generated {total_units} product units from {receipts_processed} receipts.",
            messages.SUCCESS
        )
    
    @admin.action(description="Process selected receipts")
    def process_receipts(self, request, queryset):
        """Process selected receipts"""
        processed = 0
        errors = 0
        
        for receipt in queryset:
            if receipt.is_processed:
                continue
                
            try:
                success = receipt.process_receipt()
                if success:
                    processed += 1
                else:
                    errors += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error processing receipt {receipt.id}: {str(e)}",
                    messages.ERROR
                )
                errors += 1
        
        if processed > 0:
            self.message_user(
                request,
                f"Successfully processed {processed} receipts.",
                messages.SUCCESS
            )
        
        if errors > 0:
            self.message_user(
                request,
                f"Failed to process {errors} receipts.",
                messages.WARNING
            )
    
    def save_model(self, request, obj, form, change):
        """Override save_model to set created_by and validate product fields"""
        # Validate that exactly one of product or product_family is set
        if bool(obj.product) == bool(obj.product_family):
            # If both are set or both are None
            messages.error(request, "Exactly one of Product or Product Family must be set")
            return
            
        if not change:  # Only set created_by when first created
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        
        # For new receipts, tell the user units were created
        if not change:
            from products.models import ProductUnit
            unit_count = ProductUnit.objects.filter(metadata__receipt_id=obj.id).count()
            if unit_count > 0:
                messages.success(request, f"{unit_count} Product Units were automatically created")
    
    def view_units(self, obj):
        """Provides a link to view units for this receipt"""
        from products.models import ProductUnit
        count = ProductUnit.objects.filter(metadata__receipt_id=obj.id).count()
        if count > 0:
            return format_html(
                '<a href="/admin/products/productunit/?receipt_id={}">{} Units</a>',
                obj.id, count
            )
        return "0 Units"
    
    view_units.short_description = 'Units'
    
    def view_qc(self, obj):
        """Link to quality control if it exists"""
        qc = obj.quality_control
        if qc:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:quality_control_qualitycontrol_change', args=[qc.pk]),
                "View QC"
            )
        return "-"
    
    view_qc.short_description = "Quality Control"
    
    # def formfield_for_foreignkey(self, db_field, request, **kwargs):
    #     """Customize foreign key fields in the admin form"""
    #     if db_field.name == "product":
    #         kwargs["queryset"] = Product.objects.all().order_by('name')
    #     elif db_field.name == "product_family":
    #         kwargs["queryset"] = ProductFamily.objects.all().order_by('name')
    #     return super().formfield_for_foreignkey(db_field, request, **kwargs)
