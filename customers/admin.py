from django.contrib import admin
from .models import Customer, CustomerChangeLog


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """
    Admin interface for the Customer model.
    """
    list_display = (
        'name',
        'email',
        'phone_number',
        'source_platform',
        'is_active',
        'created_at',
        'updated_at'  # additional field
    )
    search_fields = (
        'name',
        'email',
        'phone_number',
        'address'  # additional searchable field if exists
    )
    list_filter = (
        'source_platform',
        'is_active',
        'created_at',
        'updated_at'  # additional filter
    )
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': (
                'name',
                'email',
                'phone_number',
                'relay_email',
                'address',
                'source_platform',
                'is_active',
                'tags'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
        # ('Additional Info', {  # new section for extra fields
        #     'fields': ('notes',)  # make sure your model defines this field
        # }),
    )


@admin.register(CustomerChangeLog)
class CustomerChangeLogAdmin(admin.ModelAdmin):
    """
    Admin interface for the CustomerChangeLog model.
    """
    list_display = (
        'customer',
        'field_name',
        'old_value',
        'new_value',
        'updated_at'
    )
    search_fields = (
        'customer__name',
        'field_name',
        'old_value',
        'new_value'
    )
    list_filter = (
        'field_name',
        'updated_at'
    )
    ordering = ('-updated_at',)
    readonly_fields = (
        'customer',
        'field_name',
        'old_value',
        'new_value',
        'updated_at'
    )

    def has_add_permission(self, request):
        """
        Disable add permission for CustomerChangeLog as it should be auto-generated.
        """
        return False
