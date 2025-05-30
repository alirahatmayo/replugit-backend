from rest_framework import serializers
from .models import QualityControl, ProductUnitQC
from inventory.serializers import LocationSerializer
from products.serializers import ProductSerializer, ProductUnitSerializer

class QualityControlSerializer(serializers.ModelSerializer):
    """Serializer for list/create operations"""
    class Meta:
        model = QualityControl
        fields = [
            'id', 'product', 'received_quantity', 'approved_quantity', 
            'rejected_quantity', 'status', 'reference', 'batch_code', 
            'carrier', 'tracking_number', 'created_at', 'updated_at',
            'inspected_at', 'inventory_receipt'
        ]
        read_only_fields = [
            'approved_quantity', 'rejected_quantity', 'created_at', 
            'updated_at', 'inspected_at', 'inventory_receipt'
        ]

class QualityControlDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for retrieve operations"""
    product = ProductSerializer()
    created_by_name = serializers.SerializerMethodField()
    inspected_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = QualityControl
        fields = [
            'id', 'product', 'received_quantity', 'approved_quantity',
            'rejected_quantity', 'status', 'reference', 'batch_code',
            'carrier', 'tracking_number', 'supplier_info',
            'notes', 'inspection_notes', 'created_at', 'updated_at',
            'inspected_at', 'created_by', 'created_by_name',
            'inspected_by', 'inspected_by_name', 'inventory_receipt'
        ]
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None
    
    def get_inspected_by_name(self, obj):
        if obj.inspected_by:
            return obj.inspected_by.get_full_name() or obj.inspected_by.username
        return None

class ProductUnitQCSerializer(serializers.ModelSerializer):
    """Serializer for ProductUnitQC model"""
    tested_by_name = serializers.SerializerMethodField()
    unit_serial = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductUnitQC
        fields = [
            'id', 'unit', 'unit_serial', 'batch_qc', 'visual_testing', 
            'functional_testing', 'electrical_testing', 'packaging_testing',
            'measurements', 'specs', 'test_notes', 'tested_by', 'tested_by_name',
            'tested_at', 'updated_at', 'passed', 'grade', 'qc_image'
        ]
        read_only_fields = ['id', 'tested_at', 'updated_at', 'tested_by', 'passed']
    
    def get_tested_by_name(self, obj):
        if obj.tested_by:
            return obj.tested_by.get_full_name() or obj.tested_by.username
        return None
    
    def get_unit_serial(self, obj):
        if obj.unit and hasattr(obj.unit, 'serial_number'):
            return obj.unit.serial_number
        return str(obj.unit.id) if obj.unit else None
        
    def validate(self, data):
        """Validate that required fields are present"""
        # Ensure at least one test has been performed
        test_fields = [
            data.get('visual_testing', {}),
            data.get('functional_testing', {}),
            data.get('electrical_testing', {}),
            data.get('packaging_testing', {})
        ]
        
        if not any(test_fields):
            raise serializers.ValidationError("At least one test must be performed")
            
        # Ensure each test has an 'approved' key
        for i, field_name in enumerate([
            'visual_testing', 'functional_testing', 
            'electrical_testing', 'packaging_testing'
        ]):
            field_data = data.get(field_name, {})
            if field_data and 'approved' not in field_data:
                raise serializers.ValidationError(
                    f"{field_name} must include an 'approved' flag"
                )
                
        return data

class ProductUnitQCDetailSerializer(ProductUnitQCSerializer):
    """Detailed serializer for ProductUnitQC model with unit details"""
    unit = ProductUnitSerializer()