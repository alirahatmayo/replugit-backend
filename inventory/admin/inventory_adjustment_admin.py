from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html

from ..models import InventoryAdjustment

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
        from ..views_admin import approve_inventory_adjustment, reject_inventory_adjustment
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:pk>/approve/',
                self.admin_site.admin_view(approve_inventory_adjustment),
                name='approve_adjustment',
            ),
            path(
                '<uuid:pk>/reject/',
                self.admin_site.admin_view(reject_inventory_adjustment),
                name='reject_adjustment',
            ),
        ]
        return custom_urls + urls