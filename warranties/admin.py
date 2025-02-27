from django.contrib import admin
from .models import Warranty
from django.db import transaction
from django.utils.timezone import now


@admin.register(Warranty)
class WarrantyAdmin(admin.ModelAdmin):
    """
    Admin interface for the Warranty model.
    """
    list_display = (
        'product_unit', 'customer', 'order', 'status',  'warranty_period',
        'extended_period', 'warranty_expiration_date', 'is_extended', 'last_updated'
    )
    search_fields = ('product_unit__serial_number', 'customer__name', 'order__order_number', )
    list_filter = ('status', 'is_extended', 'warranty_expiration_date')
    ordering = ('-last_updated',)
    readonly_fields = ('last_updated', 'registered_at', 'warranty_expiration_date')
    fieldsets = (
        (None, {
            'fields': (
                'product_unit', 'customer', 'order', 'purchase_date',
                'warranty_period', 'extended_period', 'status', 'is_extended'
            )
        }),
        ('Dates and Logs', {
            'fields': ('registered_at', 'warranty_expiration_date', 'last_updated')
        }),
    )

    actions = ['void_warranties', 'extend_warranties']

    @admin.action(description="Void selected warranties")
    @transaction.atomic
    def void_warranties(self, request, queryset):
        for warranty in queryset:
            if warranty.status != 'void':
                warranty.transition_status('void')

    @admin.action(description="Extend selected warranties by 1 month")
    @transaction.atomic
    def extend_warranties(self, request, queryset):
        for warranty in queryset:
            try:
                warranty.extend_warranty(1)
            except Exception as e:
                self.message_user(request, f"Failed to extend warranty {warranty}: {e}", level='error')


# @admin.register(WarrantyLog)
# class WarrantyLogAdmin(admin.ModelAdmin):
#     """
#     Admin interface for the WarrantyLog model.
#     """
#     list_display = ('warranty', 'action', 'performed_at', 'details')
#     search_fields = ('warranty__product_unit__serial_number', 'action')
#     list_filter = ('action', 'performed_at')
#     ordering = ('-performed_at',)
#     readonly_fields = ('warranty', 'action', 'performed_at', 'details')

#     def has_add_permission(self, request):
#         """
#         Disable add permission for WarrantyLog as it should be auto-generated.
#         """
#         return False
