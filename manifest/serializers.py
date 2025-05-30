from rest_framework import serializers
import os
from .models import Manifest, ManifestItem, ManifestTemplate, ManifestColumnMapping, ManifestGroup
from products.models import ProductFamily


class ManifestColumnMappingSerializer(serializers.ModelSerializer):
    """Serializer for mapping columns from source to target fields"""
    class Meta:
        model = ManifestColumnMapping
        fields = '__all__'


class ManifestTemplateSerializer(serializers.ModelSerializer):
    """Serializer for manifest templates with their associated column mappings"""
    column_mappings = ManifestColumnMappingSerializer(many=True, read_only=True)
    headers = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    
    class Meta:
        model = ManifestTemplate
        fields = '__all__'
    
    def create(self, validated_data):
        # Extract headers and column mappings data from validated_data
        headers = validated_data.pop('headers', [])
        column_mappings_data = validated_data.pop('column_mappings', [])
        
        # Create the template instance
        template = ManifestTemplate.objects.create(**validated_data)
        
        # Create column mappings
        if column_mappings_data:
            for mapping_data in column_mappings_data:
                mapping_data['template'] = template
                ManifestColumnMapping.objects.create(**mapping_data)
        
        return template


class ManifestItemSerializer(serializers.ModelSerializer):
    """Serializer for individual items in a manifest"""
    status = serializers.SerializerMethodField()
    mapped_family = serializers.SerializerMethodField()
    is_family_mapped = serializers.SerializerMethodField()
    
    class Meta:
        model = ManifestItem
        fields = '__all__'
        read_only_fields = ('manifest', 'raw_data', 'mapped_data', 'error_message', 'processed_at', 'family_mapped_group')
    
    def get_status(self, obj):
        """Return the effective status which considers family mapping"""
        return obj.effective_status
    
    def get_mapped_family(self, obj):
        """Get the ProductFamily this item is mapped to"""
        if obj.mapped_family:
            from products.serializers import ProductFamilyBriefSerializer
            return ProductFamilyBriefSerializer(obj.mapped_family).data
        return None
    
    def get_is_family_mapped(self, obj):
        """Get whether this item is mapped to a family"""
        return obj.is_mapped_to_family


class ManifestGroupSerializer(serializers.ModelSerializer):
    """Serializer for groups of similar manifest items"""
    family = serializers.SerializerMethodField()
    family_mappings = serializers.SerializerMethodField()
    
    class Meta:
        model = ManifestGroup
        fields = '__all__'
    
    def get_family(self, obj):
        """Get the product family data with the expected field name 'family'"""
        if obj.product_family:
            from products.serializers import ProductFamilySerializer
            return ProductFamilySerializer(obj.product_family).data
        return None
    
    def get_family_mappings(self, obj):
        """Get family mappings data - placeholder for now"""
        # This would be expanded if there are specific family mapping relationships
        # For now, return the primary family if it exists
        if obj.product_family:
            return [{
                'family_id': obj.product_family.id,
                'is_primary': True,
                'mapped_at': None  # ManifestGroup doesn't have timestamp fields
            }]
        return []


class ManifestSerializer(serializers.ModelSerializer):
    """Basic serializer for manifest records"""
    class Meta:
        model = Manifest
        fields = '__all__'
        read_only_fields = ('uploaded_at', 'status', 'row_count', 'processed_count', 
                           'error_count', 'completed_at', 'uploaded_by')


class ManifestDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for manifest records with additional statistics"""
    items_count = serializers.SerializerMethodField()
    groups_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Manifest
        fields = '__all__'
        read_only_fields = ('uploaded_at', 'status', 'row_count', 'processed_count', 
                           'error_count', 'completed_at', 'uploaded_by')
    
    def get_items_count(self, obj):
        """Get the number of items in this manifest"""
        return obj.items.count()
    
    def get_groups_count(self, obj):
        """Get the number of groups in this manifest"""
        return obj.groups.count()


class ManifestUploadSerializer(serializers.Serializer):
    """Serializer for uploading new manifest files"""
    file = serializers.FileField()
    name = serializers.CharField(max_length=200)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, value):
        """Validate the uploaded file type (CSV or Excel only)"""
        allowed_extensions = ['.csv', '.xls', '.xlsx']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError("Unsupported file type. Please upload a CSV or Excel file.")
        return value


class ManifestMappingSerializer(serializers.Serializer):
    """Serializer for mapping columns in a manifest"""
    template_id = serializers.IntegerField(required=False)
    column_mapping = serializers.JSONField(required=False)
    column_mappings = serializers.JSONField(required=False)  # Add support for both naming conventions
    supplementary_mappings = serializers.JSONField(required=False)
    unmapped_columns = serializers.JSONField(required=False)
    
    def validate(self, data):
        """
        Validate that either template_id or column_mapping/column_mappings is provided
        """
        if 'template_id' not in data and 'column_mapping' not in data and 'column_mappings' not in data:
            raise serializers.ValidationError("Either template_id or column_mapping/column_mappings must be provided")
        return data


class ManifestBatchSerializer(serializers.Serializer):
    """Serializer for creating receipt batches from manifests"""
    location_id = serializers.IntegerField()
    reference = serializers.CharField(max_length=100, required=False)
    notes = serializers.CharField(required=False)


class ManifestGroupingSerializer(serializers.Serializer):
    """Serializer for grouping similar items in a manifest"""
    group_fields = serializers.ListField(child=serializers.CharField(), required=False)
