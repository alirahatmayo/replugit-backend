from django.contrib import admin
from .models import Order, OrderItem

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin interface for managing orders.
    Displays key order fields and organizes them into logical groups.
    """
    list_display = (
        'order_number', 
        'platform', 
        'customer', 
        'state', 
        'order_total',
        'order_date', 
        'delivery_deadline', 
        'ship_date', 
        'updated_at'
    )
    search_fields = (
        'order_number', 
        'customer__name', 
        'platform'
    )
    list_filter = (
        'platform', 
        'state', 
        'order_date', 
        'delivery_deadline', 
        'ship_date'
    )
    ordering = ('-order_date',)
    readonly_fields = ('order_date', 'updated_at', 'platform_specific_data')
    fieldsets = (
        (None, {
            'fields': (
                'order_number', 
                'customer_order_id', 
                'platform', 
                'customer', 
                'order_total',
                'state', 
                'platform_specific_data'
            )
        }),
        ('Dates', {
            'fields': (
                'order_date', 
                'delivery_deadline', 
                'ship_date'
            )
        }),
        ('Timestamps', {
            'fields': ('updated_at',)
        }),
    )

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """
    Admin interface for managing order items.
    Displays order, product, assigned product units (serial numbers), quantity,
    pricing details, status, and timestamps.
    """
    list_display = (
        'order', 
        'product', 
        'get_assigned_units', 
        'quantity', 
        'total_price', 
        'status', 
        'created_at', 
        'updated_at'
    )
    search_fields = (
        'order__order_number', 
        'product__name',
        'product__sku'
    )
    list_filter = ('status', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'price_data')
    fieldsets = (
        (None, {
            'fields': ('order', 'product', 'quantity', 'status', 'price_data', 'total_price')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def get_assigned_units(self, obj):
        """
        Returns a comma-separated string of serial numbers for the ProductUnits
        assigned to this order item. If none are assigned, returns 'N/A'.
        """
        units = obj.assigned_units  # Uses the property defined on OrderItem.
        if units.exists():
            return ", ".join(unit.serial_number for unit in units)
        return "N/A"
    get_assigned_units.short_description = "Assigned Product Units (Serial Numbers)"
