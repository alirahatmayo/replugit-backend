# products/admin.py

from django.contrib import admin
from django.contrib import messages
from .models import Product, ProductUnit, ProductUnitAssignmentHistory, ProductUnitLocationHistory, ProductFamily
from django import forms
from django.shortcuts import render

@admin.action(description="Mark selected products as sold")
def mark_products_as_sold(self, request, queryset):
    """Mark selected product units as sold through the admin interface"""
    success_count = 0
    for product_unit in queryset:
        try:
            product_unit.mark_as_sold()
            success_count += 1
        except Exception as e:
            self.message_user(request, f"Error marking {product_unit} as sold: {str(e)}", level=messages.ERROR)
    
    if success_count > 0:
        self.message_user(request, f"Successfully marked {success_count} products as sold.", level=messages.SUCCESS)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Admin interface for the Product model.
    """
    list_display = ('name', 'sku', 'product_type', 'family', 'platform', 'created_at', 'updated_at')
    search_fields = ('name', 'sku', 'product_type', 'gtin')
    list_filter = ('platform', 'product_type', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'price_data', 'regular_price', 'sale_price',  'product_type', 'gtin', 'description', 'platform', 'platform_data', 'family')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    autocomplete_fields = ['family']

@admin.register(ProductUnit)
class ProductUnitAdmin(admin.ModelAdmin):
    """
    Admin interface for the ProductUnit model.
    """
    list_display = (
        'product',
        'serial_number',
        'manufacturer_serial',
        'status',
        'is_serialized',
        'activation_code',
        'order_item',  # Show the currently assigned order item (if any)
        'location',
        'location_details',
        'created_at',
        'updated_at',
    )
    search_fields = ('serial_number', 'manufacturer_serial', 'product__name', 'product__sku', 'location__name', 'location_details__shelf', 'location_details__bin')
    list_filter = ('status', 'is_serialized', 'created_at', 'product', 'order_item', 'location')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['product', 'order_item']
    fieldsets = (
        (None, {
            'fields': ('product', 'serial_number', 'manufacturer_serial', 'activation_code', 'status', 'is_serialized', 'order_item')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Additional Information', {
            'fields': ('metadata', 'batch_code'),
            'classes': ('collapse',),  # Makes this section collapsible
        }),
    )
    actions = [mark_products_as_sold, 'create_batch']
    
    @admin.action(description="Create batch of units with unique serials")
    def create_batch(self, request, queryset):
        """Create multiple units for a product"""
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one product unit as template", level=messages.ERROR)
            return
            
        template = queryset.first()
        
        # Show form to input quantity
        class BatchForm(forms.Form):
            quantity = forms.IntegerField(min_value=1, max_value=100, 
                                         help_text="Number of units to create")
            
        if request.POST.get('apply'):
            form = BatchForm(request.POST)
            if form.is_valid():
                quantity = form.cleaned_data['quantity']
                
                from .utils import create_product_units
                try:
                    units = create_product_units(template.product.id, quantity)
                    self.message_user(
                        request, 
                        f"Created {len(units)} units with serial numbers: " +
                        ", ".join([u.serial_number for u in units]),
                        level=messages.SUCCESS
                    )
                    return
                except Exception as e:
                    self.message_user(
                        request, 
                        f"Error creating batch: {str(e)}",
                        level=messages.ERROR
                    )
                    return
        else:
            form = BatchForm()
            
        return render(
            request,
            'admin/batch_form.html',
            {
                'title': 'Create batch of product units',
                'form': form,
                'opts': self.model._meta,
            }
        )

class ReceiptFilter(admin.SimpleListFilter):
    title = 'Receipt'
    parameter_name = 'receipt_id'
    
    def lookups(self, request, model_admin):
        # Get receipts that have units
        from inventory.models import InventoryReceipt
        receipts = InventoryReceipt.objects.filter(
            id__in=ProductUnit.objects.exclude(
                metadata__receipt_id__isnull=True
            ).values('metadata__receipt_id')
        ).order_by('-receipt_date')
        return [(r.id, f"Receipt #{r.id} - {r.reference}") for r in receipts]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(metadata__receipt_id=self.value())
        return queryset

@admin.register(ProductUnitAssignmentHistory)
class ProductUnitAssignmentHistoryAdmin(admin.ModelAdmin):
    """
    Admin interface for viewing the history of product unit assignments.
    """
    list_display = ('product_unit', 'order_item', 'action', 'timestamp')
    search_fields = ('product_unit__serial_number', 'order_item__id', 'action')
    list_filter = ('action', 'timestamp')
    ordering = ('-timestamp',)
    readonly_fields = ('product_unit', 'order_item', 'action', 'timestamp', 'comments')
    fieldsets = (
        (None, {
            'fields': ('product_unit', 'order_item', 'action', 'timestamp', 'comments')
        }),
    )


@admin.register(ProductUnitLocationHistory)
class ProductUnitLocationHistoryAdmin(admin.ModelAdmin):
    """
    Admin interface for viewing the history of product unit locations.
    """
    list_display = ('product_unit', 'previous_location', 'new_location', 'timestamp')
    search_fields = ('product_unit__serial_number', 'location__name', 'location_details__shelf', 'location_details__bin')
    list_filter = ('new_location', 'timestamp', ReceiptFilter)
    ordering = ('-timestamp',)
    readonly_fields = ('product_unit', 'new_location', 'timestamp')
    fieldsets = (
        (None, {
            'fields': ('product_unit', 'new_location', 'timestamp')
        }),
    )

class ProductFamilyAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'product_type', 'is_active', 'total_quantity']
    search_fields = ['name', 'sku']
    list_filter = ['product_type', 'is_active']
    
    # def product_count(self, obj):
    #     return obj.variants.count()
    
    def total_quantity(self, obj):
        inventory = obj.total_inventory
        return inventory.get('quantity', 0) if inventory else 0

admin.site.register(ProductFamily, ProductFamilyAdmin)
