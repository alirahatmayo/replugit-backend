from rest_framework import serializers
from .models import Order, OrderItem
from products.serializers import ProductSerializer, ProductUnitSerializer
from customers.serializers import CustomerSerializer

class OrderItemDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for OrderItem including product details.
    """
    product = ProductSerializer(read_only=True)
    assigned_units = ProductUnitSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'quantity',
            'status',
            'total_price',
            'assigned_units'
        ]

class OrderItemListSerializer(serializers.ModelSerializer):
    """
    Basic serializer for OrderItem with minimal information.
    """
    product_name = serializers.CharField(source='product.name', read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'quantity', 'status', 'total_price']

class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for the OrderItem model.
    Ensures correct validation for serialized and non-serialized products.
    """
    product = ProductSerializer(read_only=True)  # Use the imported ProductSerializer
    assigned_units = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'quantity',
            'status',
            'total_price',
            'price_data',
            'assigned_units'
        ]

    def validate(self, data):
        """
        Custom validation for OrderItem to prevent duplicate serialized products.
        Optimized to reduce redundant database queries.
        """
        product_units = data.get('product_units', [])
        quantity = data.get('quantity', 1)

        if product_units:
            if quantity != len(product_units):
                raise serializers.ValidationError("The quantity must match the number of assigned serialized product units.")

            product = data['product']
            existing_order_item = OrderItem.objects.filter(
                order=data['order'], product=product, product_units__in=product_units
            ).exists()

            if existing_order_item:
                raise serializers.ValidationError(f"One or more ProductUnits are already assigned in this order.")

        return data

    def get_assigned_units(self, obj):
        return ProductUnitSerializer(obj.assigned_units, many=True).data

class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Order with complete information.
    """
    items = OrderItemDetailSerializer(many=True, read_only=True)
    customer = CustomerSerializer(read_only=True)
    total = serializers.DecimalField(source='calculate_total', read_only=True, max_digits=10, decimal_places=2)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer',
            'platform',
            'state',
            'order_date',
            'total',
            'items'
        ]

class OrderListSerializer(serializers.ModelSerializer):
    """
    Basic serializer for Order list view with essential information.
    """
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    items_count = serializers.IntegerField(source='items.count', read_only=True)
    product_skus = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer_name',
            'platform',
            'state',
            'order_total',
            'order_date',
            'items_count',
            'product_skus'
        ]

    def get_product_skus(self, obj):
        return [item.product.sku for item in obj.items.all() if hasattr(item.product, 'sku')]

class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer for the Order model.
    Includes nested OrderItem data.
    """
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer_name',
            'platform',
            'state',
            'order_total',
            'order_date',
            'items'
        ]

    def validate_state(self, value):
        """
        Validate the state transition.
        """
        valid_transitions = {
            'created': ['confirmed', 'cancelled'],
            'confirmed': ['shipped', 'cancelled'],
            'shipped': ['delivered', 'returned'],
            'delivered': ['returned'],
            'returned': [],
            'cancelled': [],
        }

        if self.instance and value not in valid_transitions.get(self.instance.state, []):
            raise serializers.ValidationError(f"Invalid state transition from {self.instance.state} to {value}.")
        return value
    
    def get_customer_name(self, obj):
        return obj.customer.name if obj.customer else 'Unknown'

