from rest_framework import serializers
from .models import Customer, CustomerChangeLog


class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for the Customer model.
    Includes validation for ensuring at least one contact field.
    """
    class Meta:
        model = Customer
        fields = '__all__'

    def validate(self, data):
        """
        Ensure at least one contact field (email, relay_email, phone_number) is provided.
        """
        if not (data.get('email') or data.get('relay_email') or data.get('phone_number')):
            raise serializers.ValidationError("At least one contact field (email, relay_email, or phone_number) must be provided.")
        return data


class CustomerChangeLogSerializer(serializers.ModelSerializer):
    """
    Serializer for the CustomerChangeLog model.
    Read-only as logs are auto-generated.
    """
    class Meta:
        model = CustomerChangeLog
        fields = '__all__'
        read_only_fields = '__all__'
