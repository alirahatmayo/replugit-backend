# products/admin.py

from django.contrib import admin
from .models import Product, ProductUnit, ProductUnitAssignmentHistory

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Admin interface for the Product model.
    """
    list_display = ('name', 'sku', 'product_type', 'gtin', 'platform', 'created_at', 'updated_at')
    search_fields = ('name', 'sku', 'product_type', 'gtin')
    list_filter = ('platform', 'product_type', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'product_type', 'gtin', 'description', 'platform', 'platform_data')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

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
        'created_at',
        'updated_at',
    )
    search_fields = ('serial_number', 'manufacturer_serial', 'product__name', 'product__sku')
    list_filter = ('status', 'is_serialized', 'created_at', 'product', 'order_item')
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
    )

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
