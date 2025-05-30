from django.contrib import admin
from django.contrib import messages
from .models import Warranty, WarrantyLog
from django.db import transaction
from django.utils.timezone import now
from django.utils.html import format_html
from django.urls import reverse
from django import forms


class WarrantyAdminForm(forms.ModelForm):
    class Meta:
        model = Warranty
        fields = '__all__'
    
    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get('customer')
        order = cleaned_data.get('order')
        product_unit = cleaned_data.get('product_unit')
        
        # # If both order and customer are specified, ensure they match
        # if order and customer and order.customer != customer:
        #     self.add_error('customer', 
        #         f"This warranty's customer ({customer}) doesn't match the order's customer ({order.customer})")
        
        # If order and product_unit are specified, ensure the product_unit belongs to this order
        if order and product_unit:
            order_items = order.items.all()
            product_belongs_to_order = False
            
            for item in order_items:
                if product_unit in item.assigned_units_relation.all():
                    product_belongs_to_order = True
                    break
            
            if not product_belongs_to_order:
                self.add_error('product_unit',
                    f"This product unit ({product_unit}) is not assigned to the specified order ({order})")
                    
        return cleaned_data


@admin.register(Warranty)
class WarrantyAdmin(admin.ModelAdmin):
    """
    Admin interface for the Warranty model.
    """
    form = WarrantyAdminForm
    list_display = (
        'product_unit', 'customer', 'order', 'status', 'warranty_period',
        'extended_period', 'warranty_expiration_date', 'is_extended', 'last_updated',
        'expiration_status'
    )
    search_fields = ('product_unit__serial_number', 'customer__name', 'order__order_number', )
    list_filter = ('status', 'is_extended', 'warranty_expiration_date')
    ordering = ('-last_updated',)
    readonly_fields = ('last_updated', 'registered_at', 'warranty_expiration_date', 'logs_link')
    fieldsets = (
        (None, {
            'fields': (
                'product_unit', 'customer', 'order', 'purchase_date',
                'warranty_period', 'extended_period', 'status', 'is_extended', 'comments'
            )
        }),
        ('Dates and Logs', {
            'fields': ('registered_at', 'warranty_expiration_date', 'last_updated', 'logs_link')
        }),
    )

    actions = ['void_warranties', 'extend_warranties', 'reset_warranties']

    def expiration_status(self, obj):
        """Display colored status based on warranty expiration"""
        if not obj.warranty_expiration_date:
            return format_html('<span style="color: gray;">Not set</span>')
            
        days_left = (obj.warranty_expiration_date - now().date()).days
        
        if obj.status == 'expired' or days_left < 0:
            return format_html('<span style="color: red; font-weight: bold;">Expired</span>')
        elif days_left < 30:
            return format_html('<span style="color: orange; font-weight: bold;">{} days left</span>', days_left)
        else:
            return format_html('<span style="color: green;">{} days left</span>', days_left)
    
    expiration_status.short_description = 'Expiration'

    def logs_link(self, obj):
        """Display link to warranty logs"""
        if obj.id:
            logs_count = obj.logs.count()
            if logs_count:
                url = reverse('admin:warranties_warrantylog_changelist') + f'?warranty__id__exact={obj.id}'
                return format_html('<a href="{}">View {} log entries</a>', url, logs_count)
            return "No logs yet"
        return "N/A"
    
    logs_link.short_description = "Warranty Logs"

    @admin.action(description="Void selected warranties")
    @transaction.atomic
    def void_warranties(self, request, queryset):
        count = 0
        for warranty in queryset:
            if warranty.status != 'void':
                try:
                    warranty.transition_status('void', user=request.user)
                    count += 1
                except Exception as e:
                    self.message_user(request, f"Failed to void warranty {warranty}: {e}", level=messages.ERROR)
        
        if count > 0:
            self.message_user(request, f"Successfully voided {count} warranties.", level=messages.SUCCESS)

    @admin.action(description="Extend selected warranties by 1 month")
    @transaction.atomic
    def extend_warranties(self, request, queryset):
        count = 0
        for warranty in queryset:
            try:
                warranty.extend_warranty(1)
                # Log the extension
                warranty.logs.create(
                    action='extended',
                    performed_by=request.user,
                    details=f"Extended warranty by 1 month via admin action"
                )
                count += 1
            except Exception as e:
                self.message_user(request, f"Failed to extend warranty {warranty}: {e}", level=messages.ERROR)
        
        if count > 0:
            self.message_user(request, f"Successfully extended {count} warranties by 1 month.", level=messages.SUCCESS)

    @admin.action(description="Reset selected warranties")
    @transaction.atomic
    def reset_warranties(self, request, queryset):
        """Reset warranties to not_registered status for reuse"""
        count = 0
        for warranty in queryset:
            try:
                # Flag this as an admin edit to prevent double logging
                warranty._admin_edit = True
                
                # Use a default reason since we're not collecting it through a form
                warranty.reset_warranty(
                    user=request.user,
                    reason="Reset via admin action",
                    keep_customer=False  # Default to not keeping customer
                )
                count += 1
            except Exception as e:
                self.message_user(request, f"Failed to reset warranty {warranty}: {e}", level=messages.ERROR)
        
        if count > 0:
            self.message_user(request, f"Successfully reset {count} warranties.", level=messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        """
        Override default save_model to track changes in the admin panel.
        This ensures all admin edits are properly logged.
        """
        if change:
            # Add flag to prevent double logging
            obj._admin_edit = True
            
            # Get original object for comparison
            try:
                old_obj = Warranty.objects.get(pk=obj.pk)
                changed_fields = []
                
                # Track important field changes
                important_fields = [
                    'customer', 'purchase_date', 'warranty_period', 
                    'extended_period', 'is_extended', 'comments'
                ]
                
                for field in important_fields:
                    old_value = getattr(old_obj, field)
                    new_value = getattr(obj, field)
                    
                    if old_value != new_value:
                        changed_fields.append(f"{field}: {old_value} → {new_value}")
                
                # Handle status change separately to prevent duplicate logging
                status_changed = old_obj.status != obj.status
                old_status = old_obj.status
                
                # Call the default save_model method first
                super().save_model(request, obj, form, change)
                
                # If important fields changed (except status), create a log entry
                if changed_fields:
                    WarrantyLog.objects.create(
                        warranty=obj,
                        action='admin_edit',
                        performed_by=request.user,
                        details=f"Admin edited: {', '.join(changed_fields)}"
                    )
                    
                # Handle status change separately
                if status_changed:
                    WarrantyLog.objects.create(
                        warranty=obj,
                        action=obj.status,  # Use the new status as the action
                        performed_by=request.user,
                        details=f"Status changed from {old_status} to {obj.status} via admin"
                    )
            except Warranty.DoesNotExist:
                # New warranty, call default save
                super().save_model(request, obj, form, change)
                
                # Log the creation
                WarrantyLog.objects.create(
                    warranty=obj,
                    action='created',
                    performed_by=request.user,
                    details=f"Warranty created via admin"
                )
        else:
            # New warranty
            super().save_model(request, obj, form, change)
            
            # Log the creation
            WarrantyLog.objects.create(
                warranty=obj,
                action='created',
                performed_by=request.user,
                details=f"Warranty created via admin"
            )


@admin.register(WarrantyLog)
class WarrantyLogAdmin(admin.ModelAdmin):
    """
    Admin interface for the WarrantyLog model.
    """
    list_display = ('warranty', 'action', 'performed_at', 'performed_by', 'details')
    search_fields = ('warranty__product_unit__serial_number', 'action', 'details')
    list_filter = ('action', 'performed_at', 'performed_by')
    ordering = ('-performed_at',)
    readonly_fields = ('warranty', 'action', 'performed_at', 'performed_by', 'details')
    
    def has_add_permission(self, request):
        """Disable add permission for WarrantyLog as it should be auto-generated."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable change permission for WarrantyLog to maintain audit integrity."""
        return False
