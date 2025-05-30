from django.contrib import admin
from .models import Order, OrderItem, OrderStatusHistory

# Define the inline class first
class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('previous_status', 'new_status', 'changed_at', 'changed_by', 'reason')
    can_delete = False
    max_num = 0
    verbose_name_plural = "Status History"

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
    inlines = [OrderStatusHistoryInline]

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
    readonly_fields = ('created_at', 'updated_at', 'price_data', 'get_tax_summary')
    fieldsets = (
        (None, {
            'fields': ('order', 'product', 'quantity', 'status', 'total_price')
        }),
        ('Price Details', {
            'fields': ('price_data', 'get_tax_summary'),
            'classes': ('collapse',),
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
        try:
            units = obj.assigned_units  # This is a property that returns a queryset
            if units and units.exists():
                return ", ".join(str(getattr(unit, 'serial_number', '')) for unit in units)
            return "N/A"
        except Exception as e:
            return f"Error: {str(e)}"
    get_assigned_units.short_description = "Assigned Product Units (Serial Numbers)"

    def get_tax_summary(self, obj):
        """Display tax summary if available"""
        if obj.price_data and 'tax_summary' in obj.price_data:
            summary = []
            for tax_name, amount in obj.price_data['tax_summary'].items():
                summary.append(f"{tax_name}: ${amount}")
            return ", ".join(summary)
        return "No tax details"
    get_tax_summary.short_description = "Tax Summary"

@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'previous_status', 'new_status', 'changed_at', 'changed_by')
    list_filter = ('new_status', 'changed_at', 'changed_by')
    search_fields = ('order__order_number', 'order__customer__name')
    date_hierarchy = 'changed_at'
    readonly_fields = ('order', 'previous_status', 'new_status', 'changed_at')
