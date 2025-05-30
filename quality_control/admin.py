from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.contrib import messages


from .models import QualityControl, QualityControlStatus, ProductUnitQC, ProductQCTemplate
# from .models import ProductQCTemplate

from inventory.models import Location, InventoryReceipt

@admin.register(QualityControl)
class QualityControlAdmin(admin.ModelAdmin):
    """Admin interface for quality control workflow"""
    list_display = ('id', 'product', 'received_quantity', 'approved_quantity', 
                    'rejected_quantity', 'status', 'created_at', 'inspected_by', 'receipt_status')
    list_filter = ('status', 'created_at', 'product')
    search_fields = ('reference', 'notes', 'product__name', 'product__sku', 'batch_code')
    readonly_fields = ('created_at', 'updated_at', 'inspected_at', 'inventory_receipt')
    
    fieldsets = (
        (None, {
            'fields': ('product', 'received_quantity', 'reference', 'batch_code')
        }),
        ('Shipping Information', {
            'fields': ('carrier', 'tracking_number'),
            'classes': ('collapse',)
        }),
        ('Inspection Details', {
            'fields': ('status', 'approved_quantity', 'rejected_quantity', 
                       'notes', 'inspection_notes', 'inspected_by', 'inspected_at')
        }),
        ('Supplier Information', {
            'fields': ('supplier_info',),
            'classes': ('collapse',)
        }),
        ('Inventory', {
            'fields': ('inventory_receipt',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Set created_by on new quality controls"""
        if not change:  # Only set created_by when first created
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def receipt_status(self, obj):
        """Show inventory receipt status"""
        if not obj.inventory_receipt:
            if obj.status in [QualityControlStatus.APPROVED, QualityControlStatus.PARTIALLY_APPROVED]:
                return format_html(
                    '<a href="{}" class="button">Create Receipt</a>',
                    reverse('admin:create_receipt_from_qc', args=[obj.pk])
                )
            return "No receipt"
        
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:inventory_inventoryreceipt_change', args=[obj.inventory_receipt.pk]),
            "View Receipt"
        )
    
    receipt_status.short_description = "Inventory Receipt"
    
    def get_urls(self):
        # Use lazy import to avoid circular imports
        from . import views_admin
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:pk>/inspect/',
                self.admin_site.admin_view(views_admin.inspect_quality_control),
                name='inspect_qc',
            ),
            path(
                '<uuid:pk>/create-receipt/',
                self.admin_site.admin_view(views_admin.create_inventory_receipt),
                name='create_receipt_from_qc',
            ),
        ]
        return custom_urls + urls

@admin.register(ProductUnitQC)
class ProductUnitQCAdmin(admin.ModelAdmin):
    """Admin interface for Product Unit QC"""
    list_display = ('unit', 'passed', 'grade', 'get_test_summary', 'tested_by', 'tested_at')
    list_filter = ('passed', 'grade', 'tested_by', 'tested_at')
    search_fields = ('unit__serial_number', 'test_notes')
    readonly_fields = ('tested_at', 'updated_at', 'passed')
    
    fieldsets = (
        (None, {
            'fields': ('unit', 'batch_qc', 'grade', 'passed')
        }),
        ('Testing Details', {
            'fields': (
                'visual_testing', 'functional_testing', 
                'electrical_testing', 'packaging_testing'
            )
        }),
        ('Specifications & Measurements', {
            'fields': ('measurements', 'specs', 'qc_image')
        }),
        ('Notes & Metadata', {
            'fields': ('test_notes', 'tested_by', 'tested_at', 'updated_at')
        }),
    )
    
    def get_test_summary(self, obj):
        """Get summary of tests performed"""
        tests = []
        if obj.visual_testing and obj.visual_testing.get('approved') is not None:
            tests.append('Visual')
        if obj.functional_testing and obj.functional_testing.get('approved') is not None:
            tests.append('Func')
        if obj.electrical_testing and obj.electrical_testing.get('approved') is not None:
            tests.append('Elec')
        if obj.packaging_testing and obj.packaging_testing.get('approved') is not None:
            tests.append('Pack')
            
        return ', '.join(tests) if tests else 'No tests'
    
    get_test_summary.short_description = 'Tests'

@admin.register(ProductQCTemplate)
class ProductQCTemplateAdmin(admin.ModelAdmin):
    """Admin interface for Product QC Templates"""
    list_display = ('name', 'product_type_name', 'is_active', 'created_by', 'created_at')  # Changed to product_type_name
    list_filter = ('is_active', 'product_type_name', 'created_at')  # Changed to product_type_name
    search_fields = ('name', 'product_type_name')  # Changed to product_type_name
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'product_type_name', 'is_active')  # Changed to product_type_name
        }),
        ('Required Tests', {
            'fields': (
                'visual_testing_required', 'functional_testing_required',
                'electrical_testing_required', 'packaging_testing_required'
            )
        }),
        ('Test Templates', {
            'fields': (
                'visual_testing_template', 'functional_testing_template',
                'electrical_testing_template', 'packaging_testing_template',
                'measurements_template', 'specs_template'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by when first created
            obj.created_by = request.user
        super().save_model(request, obj, form, change)