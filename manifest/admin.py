from django.contrib import admin
from .models import Manifest, ManifestItem, ManifestTemplate, ManifestColumnMapping, ManifestGroup

@admin.register(Manifest)
class ManifestAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'uploaded_at', 'row_count', 'processed_count', 'error_count', 'uploaded_by')
    list_filter = ('status', 'uploaded_at', 'file_type')
    search_fields = ('name', 'reference', 'notes')
    date_hierarchy = 'uploaded_at'
    readonly_fields = ('uploaded_at', 'row_count', 'processed_count', 'error_count', 'completed_at')

@admin.register(ManifestItem)
class ManifestItemAdmin(admin.ModelAdmin):
    list_display = ('manifest', 'row_number', 'effective_status', 'model', 'manufacturer', 'mapped_family_name', 'processor', 'memory', 'storage')
    list_filter = ('status', 'manifest', 'condition_grade', 'has_battery', 'family_mapped_group')
    search_fields = ('barcode', 'serial', 'model', 'manufacturer')
    raw_id_fields = ('manifest', 'batch_item', 'group', 'family_mapped_group')
    
    def effective_status(self, obj):
        """Show the effective status (considering family mapping)"""
        return obj.effective_status
    effective_status.short_description = "Status"
    
    def mapped_family_name(self, obj):
        """Show the mapped family name"""
        return obj.mapped_family.name if obj.mapped_family else "-"
    mapped_family_name.short_description = "Mapped Family"

class ManifestColumnMappingInline(admin.TabularInline):
    model = ManifestColumnMapping
    extra = 1

@admin.register(ManifestTemplate)
class ManifestTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at', 'updated_at', 'is_default')
    list_filter = ('is_default', 'created_at')
    search_fields = ('name', 'description')
    inlines = [ManifestColumnMappingInline]

@admin.register(ManifestGroup)
class ManifestGroupAdmin(admin.ModelAdmin):
    list_display = ('manifest', 'manufacturer', 'model', 'quantity', 'primary_family')
    list_filter = ('manifest', 'product_family')
    search_fields = ('manufacturer', 'model', 'notes', 'product_family__name')
    raw_id_fields = ('manifest', 'product_family', 'batch_item')
    
    def primary_family(self, obj):
        """Display the primary family name"""
        return obj.product_family.name if obj.product_family else "-"
    
    primary_family.short_description = "Primary Family"
