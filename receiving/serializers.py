from rest_framework import serializers
from django.db import transaction
from .models import ReceiptBatch, BatchItem
from products.models import Product
from inventory.models import InventoryReceipt
from products.serializers import ProductSerializer, ProductMinimalSerializer
# Import with an alias to avoid namespace conflicts
from inventory.serializers import InventoryReceiptSerializer as InventoryReceiptBaseSerializer


class BatchItemSerializer(serializers.ModelSerializer):
    """Serializer for batch items"""
    product_name = serializers.SerializerMethodField()
    product_sku = serializers.SerializerMethodField()
    
    class Meta:
        model = BatchItem
        fields = [
            'id', 'product', 'product_family', 'product_name', 'product_sku',
            'quantity', 'unit_cost', 'notes', 'destination', 'requires_unit_qc',
            'create_product_units', 'skip_inventory_receipt',
            'is_processed'
        ]
    
    def get_product_name(self, obj):
        """Get product name based on product or product_family"""
        if obj.product:
            return obj.product.name
        elif obj.product_family:
            return obj.product_family.name
        return None
    
    def get_product_sku(self, obj):
        """Get product SKU based on product or product_family"""
        if obj.product:
            return obj.product.sku
        elif obj.product_family:
            return obj.product_family.sku
        return None
        
    def validate(self, data):
        """Validate that exactly one of product or product_family is provided"""
        product = data.get('product')
        product_family = data.get('product_family')
        
        if not product and not product_family:
            raise serializers.ValidationError("Either product or product_family must be provided")
            
        if product and product_family:
            raise serializers.ValidationError("Only one of product or product_family can be provided")
            
        return data


class ReceiptBatchSerializer(serializers.ModelSerializer):
    """Serializer for listing receipt batches"""
    location_name = serializers.ReadOnlyField(source='location.name')
    receipt_count = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    created_by_username = serializers.ReadOnlyField(source='created_by.username')
    
    class Meta:
        model = ReceiptBatch
        fields = [
            'id', 'batch_code', 'reference', 'receipt_date', 'location', 
            'location_name', 'status', 'receipt_count', 'total_items',
            'total_cost', 'currency', 'shipping_carrier', 'shipping_tracking',
            'created_by_username'
        ]
    
    def get_receipt_count(self, obj):
        """Get number of distinct items in batch"""
        return obj.items.count()
    
    def get_total_items(self, obj):
        """Get total quantity of all items"""
        return obj.total_items

# This is a custom serializer for rendering inventory receipts in the context of a batch
# Renamed to avoid conflicts with the imported one
class ReceiptBatchBriefSerializer(serializers.ModelSerializer):
    """Brief serializer for receipt batches with minimal fields"""
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = ReceiptBatch
        fields = [
            'id', 'batch_code', 'reference', 'status',
            'location', 'location_name', 'receipt_date'
        ]

class ReceiptItemCreateSerializer(serializers.Serializer):
    """Serializer for creating batch items"""
    product = serializers.UUIDField(required=False)
    product_family = serializers.UUIDField(required=False)
    quantity = serializers.IntegerField(min_value=1)
    unit_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    requires_unit_qc = serializers.BooleanField(default=False)
    create_product_units = serializers.BooleanField(default=True)
    skip_inventory_receipt = serializers.BooleanField(default=False)
    
    def validate(self, data):
        """Validate that exactly one of product or product_family is provided"""
        from .validation import validate_product_fields
        return validate_product_fields(data)


class ReceiptBatchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating receipt batches with items"""
    items = ReceiptItemCreateSerializer(many=True, required=False, default=list)
    
    class Meta:
        model = ReceiptBatch
        fields = [
            'reference', 'location', 'receipt_date', 'notes',
            'shipping_tracking', 'shipping_carrier', 'seller_info',
            'currency', 'items'
        ]
    
    def validate_items(self, items):
        """Validate items in the batch if provided"""
        # Only validate items if they're provided
        if items and all(item.get('skip_inventory_receipt', False) for item in items):
            raise serializers.ValidationError(
                "At least one item must create an inventory receipt."
            )
        return items
    
    def validate_location(self, location):
        """Validate location exists"""
        if not location:
            raise serializers.ValidationError("Location is required")
        return location
    
    @transaction.atomic
    def create(self, validated_data):
        """Create batch with receipt items"""
        items_data = validated_data.pop('items')
        
        # Add created_by from context
        validated_data['created_by'] = self.context['request'].user
        
        # Create the batch
        batch = ReceiptBatch.objects.create(**validated_data)
          # Create batch items and inventory receipts
        for item_data in items_data:
            # Create the batch item first
            batch_item_args = {
                'batch': batch,
                'quantity': item_data['quantity'],
                'unit_cost': item_data.get('unit_cost'),
                'notes': item_data.get('notes', ''),
                'requires_unit_qc': item_data.get('requires_unit_qc', False),
                'create_product_units': item_data.get('create_product_units', True),
                'skip_inventory_receipt': item_data.get('skip_inventory_receipt', False)
            }
            
            # Assign either product or product_family
            if 'product' in item_data and item_data['product']:
                batch_item_args['product_id'] = item_data['product']
            elif 'product_family' in item_data and item_data['product_family']:
                batch_item_args['product_family_id'] = item_data['product_family']
                
            batch_item = BatchItem.objects.create(**batch_item_args)
              # Create inventory receipt if not skipped
            if not batch_item.skip_inventory_receipt:
                receipt_data = {
                    'quantity': item_data['quantity'],
                    'location': batch.location,
                    'unit_cost': item_data.get('unit_cost'),
                    'requires_unit_qc': item_data.get('requires_unit_qc', False),
                    'create_product_units': item_data.get('create_product_units', True),
                    'is_processed': False,
                    'reference': batch.reference,
                    'batch_code': batch.batch_code,
                    'batch': batch,  # Keep this for backward compatibility
                    'created_by': self.context['request'].user,
                    'notes': item_data.get('notes', '')
                }
                
                # Assign either product or product_family
                if 'product' in item_data and item_data['product']:
                    receipt_data['product_id'] = item_data['product']
                elif 'product_family' in item_data and item_data['product_family']:
                    receipt_data['product_family_id'] = item_data['product_family']
                
                inventory_receipt = InventoryReceipt.objects.create(**receipt_data)
                
                # Set the one-way relationship
                batch_item.inventory_receipt = inventory_receipt
                batch_item.save(update_fields=['inventory_receipt'])
        
        # Update batch totals
        batch.calculate_totals()
        
        return batch


class BatchItemListSerializer(serializers.ModelSerializer):
    """Serializer for batch items in list views"""
    product_detail = ProductMinimalSerializer(source='product', read_only=True)  # Use minimal serializer
    is_processed = serializers.ReadOnlyField()
    inventory_receipt_id = serializers.UUIDField(source='inventory_receipt.id', read_only=True)
    
    class Meta:
        model = BatchItem
        fields = [
            'id','batch', 'product', 'product_detail', 'quantity', 
            'unit_cost', 'total_cost', 'is_processed',
            'inventory_receipt_id'
        ]  # Only include essential fields for list view


class ReceiptBatchDetailSerializer(ReceiptBatchSerializer):
    """Detailed serializer for a single receipt batch including items"""
    # Use the list serializer to keep responses smaller
    items = BatchItemListSerializer(many=True, read_only=True)
    inventory_receipts = InventoryReceiptBaseSerializer(source='receipts', many=True, read_only=True)
    
    class Meta(ReceiptBatchSerializer.Meta):
        fields = ReceiptBatchSerializer.Meta.fields + [
            'items', 'inventory_receipts', 'notes', 'seller_info', 'completed_at'
        ]


# This is a custom serializer for rendering inventory receipts in the context of a batch
# Renamed to avoid conflicts with the imported one
class BatchInventoryReceiptSerializer(serializers.ModelSerializer):
    """Serializer for inventory receipts within a batch view"""
    product_name = serializers.ReadOnlyField(source='product.name')
    product_sku = serializers.ReadOnlyField(source='product.sku')
    product_detail = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        from inventory.models import InventoryReceipt
        model = InventoryReceipt
        fields = [
            'id', 'product', 'product_detail', 'product_name', 'product_sku', 'quantity',
            'reference', 'batch_code', 'unit_cost', 'total_cost',
            'requires_unit_qc', 'create_product_units', 'receipt_date',
            'is_processed'
        ]


class BatchSerializer(serializers.ModelSerializer):
    """Serializer for the generic batch viewset"""
    
    class Meta:
        model = ReceiptBatch  # Using ReceiptBatch as the model since there's no separate Batch model
        fields = [
            'id', 'batch_code', 'reference', 'receipt_date', 'location', 
            'status', 'total_cost', 'currency', 'notes'
        ]
        
        
class BatchItemDestinationSerializer(serializers.Serializer):
    """Serializer for updating batch item destination"""
    destination = serializers.ChoiceField(choices=BatchItem.DESTINATION_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)