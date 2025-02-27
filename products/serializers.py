from rest_framework import serializers
from .models import Product, ProductUnit


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for the Product model.
    """
    class Meta:
        model = Product
        fields = '__all__'


class ProductUnitSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProductUnit model.
    Validates lifecycle and state transitions.
    """
    class Meta:
        model = ProductUnit
        fields = '__all__'

    def validate(self, data):
        """
        Custom validation for ProductUnit states.
        """
        if data['status'] == 'assigned' and not data.get('serial_number'):
            raise serializers.ValidationError("Assigned units must have a serial number.")
        if not data['is_serialized'] and data.get('serial_number'):
            raise serializers.ValidationError("Non-serialized products should not have a serial number.")
        return data
