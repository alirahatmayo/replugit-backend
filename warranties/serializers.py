from rest_framework import serializers
from .models import Warranty, WarrantyLog
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action


class WarrantySerializer(serializers.ModelSerializer):
    """
    Serializer for the Warranty model.
    Includes validation and calculated fields for expiration.
    """
    product_name = serializers.CharField(source='product_unit.product.name', read_only=True)
    product_serial_number = serializers.CharField(source='product_unit.serial_number', read_only=True)
    product_sourced_platform = serializers.CharField(source='product_unit.product.platform', read_only=True)

    days_until_expiration = serializers.SerializerMethodField()

    class Meta:
        model = Warranty
        fields = '__all__'

    def get_days_until_expiration(self, obj):
        """
        Calculate the number of days until the warranty expires.
        """
        if obj.warranty_expiration_date:
            return (obj.warranty_expiration_date - obj.last_updated.date()).days
        return None

    def validate_status(self, value):
        """
        Validate state transitions.
        """
        valid_transitions = {
            'not_registered': ['active', 'void'],
            'active': ['expired', 'void'],
            'expired': ['void'],
            'void': [],
        }

        instance = self.instance
        if instance and value not in valid_transitions.get(instance.status, []):
            raise serializers.ValidationError(f"Invalid status transition from {instance.status} to {value}.")
        return value

    # @action(detail=False, methods=['get'], url_path='check/(?P<serial_number>[^/.]+)')
    # def check_warranty(self, request, serial_number=None):
    #     """
    #     Check warranty status using the ProductUnit serial number.
    #     """
    #     try:
    #         warranty = Warranty.objects.select_related('product_unit').get(product_unit__serial_number=serial_number)
    #         serializer = self.get_serializer(warranty)
    #         return Response(serializer.data, status=status.HTTP_200_OK)
    #     except Warranty.DoesNotExist:
    #         return Response({'error': 'No warranty found for the provided serial number.'}, status=status.HTTP_404_NOT_FOUND)


class WarrantyLogSerializer(serializers.ModelSerializer):
    """
    Serializer for the WarrantyLog model.
    """
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True)

    class Meta:
        model = WarrantyLog
        fields = '__all__'
