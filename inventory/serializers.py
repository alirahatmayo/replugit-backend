from rest_framework import serializers
from products.serializers import ProductSerializer, ProductUnitSerializer
from .models import Inventory, Location, InventoryHistory, StockAlert, InventoryAdjustment, InventoryReceipt

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'

class InventorySerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = Inventory
        fields = '__all__'

class InventoryDetailSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    
    class Meta:
        model = Inventory
        fields = '__all__'

class InventoryHistorySerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source='inventory.product.sku', read_only=True)
    location_name = serializers.CharField(source='inventory.location.name', read_only=True)
    adjusted_by_name = serializers.CharField(source='adjusted_by.username', read_only=True)
    
    class Meta:
        model = InventoryHistory
        fields = [
            'id', 'product_sku', 'location_name', 'previous_quantity', 
            'new_quantity', 'change', 'timestamp', 'reason', 
            'reference', 'notes', 'adjusted_by_name'
        ]

class StockAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = StockAlert
        fields = '__all__'

class InventoryAdjustmentSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source='inventory.product.sku', read_only=True)
    location_name = serializers.CharField(source='inventory.location.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    
    class Meta:
        model = InventoryAdjustment
        fields = '__all__'
        read_only_fields = ['approved_by', 'approved_at', 'status']

class InventoryUpdateSerializer(serializers.Serializer):
    sku = serializers.CharField(required=True)
    platform = serializers.CharField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=0)
    location = serializers.CharField(required=False)
    reason = serializers.CharField(required=False, default='MANUAL')
    reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

class InventoryReceiptSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = InventoryReceipt
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'quantity',
            'location', 'location_name', 'receipt_date', 'reference',
            'notes', 'batch_code', 'created_by', 'created_by_name',
            'seller_info', 'unit_cost', 'total_cost', 'currency',
            'shipping_tracking', 'shipping_carrier'
        ]
    
    def validate(self, data):
        """
        Validate that the product exists and other business rules.
        """
        if 'product' not in data:
            raise serializers.ValidationError("Product is required")
            
        if 'location' not in data:
            raise serializers.ValidationError("Location is required")
            
        if 'quantity' not in data or data['quantity'] <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
            
        # Validate seller_info structure if provided
        seller_info = data.get('seller_info')
        if seller_info:
            if not isinstance(seller_info, dict):
                raise serializers.ValidationError("seller_info must be a JSON object")
                
            # Check for required seller fields
            if 'name' not in seller_info and 'company_name' not in seller_info:
                raise serializers.ValidationError("seller_info must include 'name' or 'company_name'")
                
        return data

class ReceiptWithUnitsSerializer(serializers.Serializer):
    """Serializer for receipt with its units"""
    receipt = InventoryReceiptSerializer()
    units_created = serializers.IntegerField()
    units = ProductUnitSerializer(many=True)

class InventoryDashboardSerializer(serializers.Serializer):
    """Serializer for dashboard data"""
    summary = serializers.DictField()
    top_products = serializers.ListField(child=serializers.DictField())
    recent_activity = InventoryHistorySerializer(many=True)
    recent_receipts = InventoryReceiptSerializer(many=True)
    status_counts = serializers.DictField()