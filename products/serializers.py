from rest_framework import serializers
from .models import Product, ProductUnit, ProductFamily
from inventory.models import Inventory


class SimpleInventorySerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for basic inventory information.
    """
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = Inventory
        fields = [
            'id', 'location_name', 'quantity', 'available_quantity', 
            'reserved_quantity', 'status'
        ]


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for the Product model.
    Includes inventory information.
    """
    inventory = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'
    
    def get_inventory(self, obj):
        """
        Get inventory information for this product across all locations.
        """
        inventories = obj.inventory_records.all()
        serializer = SimpleInventorySerializer(inventories, many=True)
        return serializer.data


class ProductMinimalSerializer(serializers.ModelSerializer):
    """Minimal product serializer for use in list views"""
    class Meta:
        model = Product
        fields = ['id', 'product_type','sku', 'name']  # Only include essential fields


class ProductUnitSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for the ProductUnit model.
    Includes related product and order information.
    """
    # Related fields
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_type = serializers.CharField(source='product.product_type', read_only=True)
    order_number = serializers.SerializerMethodField()
    order_item_quantity = serializers.SerializerMethodField()
    warranty_status = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductUnit
        fields = [
            'id', 'serial_number', 'manufacturer_serial', 'status', 'is_serialized',
            'activation_code', 'order_item', 'created_at', 'updated_at',
            # Related fields
            'product', 'product_sku', 'product_name', 'product_type', 
            'order_number', 'order_item_quantity', 'warranty_status'
        ]
        read_only_fields = ['activation_code', 'created_at', 'updated_at']
        
    def get_order_number(self, obj):
        """Get the order number from the related order item."""
        if obj.order_item and hasattr(obj.order_item, 'order') and obj.order_item.order:
            return obj.order_item.order.order_number
        return None
    
    def get_order_item_quantity(self, obj):
        """Get quantity from the related order item."""
        if obj.order_item:
            return obj.order_item.quantity
        return None
    
    def get_warranty_status(self, obj):
        """Get warranty status if this unit has one."""
        try:
            warranty = obj.warranty
            if warranty:
                return {
                    'status': warranty.status,
                    'expiration_date': warranty.warranty_expiration_date,
                    'is_extended': warranty.is_extended,
                }
        except:
            pass
        return None
        
    def validate(self, data):
        """
        Custom validation for ProductUnit states.
        """
        # Check if this is a creation or update
        is_update = self.instance is not None
        
        # Validate serialization status
        if 'status' in data and 'is_serialized' in data:
            if data['status'] == 'assigned' and not data.get('is_serialized', False):
                raise serializers.ValidationError("Only serialized products can be assigned.")
        
        # Validate serial number requirements
        if ('is_serialized' in data and data['is_serialized']) and not data.get('serial_number') and not is_update:
            # For new serialized products, we'll auto-generate in the model's save method
            pass
            
        # Validate serial number for non-serialized products
        if 'is_serialized' in data and not data['is_serialized'] and data.get('serial_number'):
            raise serializers.ValidationError("Non-serialized products should not have a serial number.")
        
        # Validate order item assignment
        if 'order_item' in data and data['order_item'] and 'product' in data:
            if data['product'] != data['order_item'].product:
                raise serializers.ValidationError(
                    "ProductUnit's product must match the product of its assigned OrderItem."
                )
                
        return data


class ProductUnitListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for ProductUnit lists.
    Includes essential info without heavy related fields.
    """
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    order_number = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductUnit
        fields = [
            'id', 'serial_number', 'status', 'is_serialized', 
            'product_sku', 'product_name', 'order_number',
            'created_at'
        ]
        
    def get_order_number(self, obj):
        """Get the order number from the related order item."""
        if obj.order_item and hasattr(obj.order_item, 'order') and obj.order_item.order:
            return obj.order_item.order.order_number
        return None


class ProductUnitBulkCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for bulk creation of product units.
    """
    quantity = serializers.IntegerField(write_only=True, min_value=1, max_value=100)
    product_sku = serializers.CharField(write_only=True)
    
    class Meta:
        model = ProductUnit
        fields = ['product_sku', 'quantity', 'status', 'is_serialized']
        
    def validate_product_sku(self, value):
        """Validate that product with given SKU exists."""
        try:
            Product.objects.get(sku=value)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError(f"Product with SKU '{value}' does not exist.")
        
    def create(self, validated_data):
        """Create multiple product units."""
        from .utils import create_product_units
        
        product_sku = validated_data.pop('product_sku')
        quantity = validated_data.pop('quantity')
        
        # Get product by SKU
        product = Product.objects.get(sku=product_sku)
        
        # Set common attributes for all units
        status = validated_data.get('status', 'in_stock')
        is_serialized = validated_data.get('is_serialized', True)
        
        units = []
        for _ in range(quantity):
            unit = ProductUnit(
                product=product,
                status=status,
                is_serialized=is_serialized
            )
            unit.save()  # This will auto-generate the serial


class ProductFamilySerializer(serializers.ModelSerializer):
    """Serializer for ProductFamily model"""
    product_count = serializers.SerializerMethodField()
    total_inventory = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductFamily
        fields = [
            'id', 'name', 'sku', 'description', 'manufacturer', 'model',
            'product_type', 'attributes', 'category', 'keywords',
            'is_active', 'created_at', 'updated_at', 'product_count',
            'total_inventory'
        ]
    
    def get_product_count(self, obj):
        """Get count of products in this family"""
        return obj.products.count()
    
    def get_total_inventory(self, obj):
        """Get total inventory for this family"""
        inventory = obj.total_inventory
        return {
            'quantity': inventory.get('quantity', 0),
            'available': inventory.get('available', 0)
        }


class ProductFamilyBriefSerializer(serializers.ModelSerializer):
    """Brief serializer for ProductFamily with minimal fields"""
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductFamily
        fields = ['id', 'name', 'sku', 'product_type', 'product_count']
    
    def get_product_count(self, obj):
        """Get count of products in this family"""
        return obj.products.count()
