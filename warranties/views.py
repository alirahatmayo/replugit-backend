# warranty/views.py
from rest_framework import viewsets, filters, status, routers
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.urls import path, include
from django.db import transaction, models
import logging
from datetime import timedelta
from django.utils.timezone import now

from .models import Warranty
from products.models import ProductUnit
from customers.models import Customer
from .serializers import WarrantySerializer

logger = logging.getLogger(__name__)

class WarrantyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Warranties.
    Includes filtering, searching, and custom actions for activation, extension, status checks, and validation.
    """
    queryset = Warranty.objects.select_related('product_unit').prefetch_related('customer', 'order').all()
    pagination_class = PageNumberPagination
    serializer_class = WarrantySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_extended', 'customer', 'warranty_expiration_date']
    search_fields = ['product_unit__serial_number', 'customer__name', 'order__order_number']
    ordering_fields = ['warranty_expiration_date', 'last_updated']
    ordering = ['-last_updated']

    @transaction.atomic
    @action(detail=False, methods=['post'], url_path='activate/(?P<serial_number>[^/.]+)')
    def activate(self, request, serial_number):
        """
        Activate a warranty by verifying the serial number and activation code.
        If the customer does not exist, create a new customer.
        """
        try:
            data = request.data
            activation_code = data.get("activation_code")
            name = data.get("name")
            email = data.get("email")
            phone_number = data.get("phone_number")

            # Ensure required fields are provided
            missing_fields = [field for field in ["activation_code", "serial_number", "name", "phone_number"] if not data.get(field)]
            if missing_fields:
                return Response({'error': f'Missing fields: {", ".join(missing_fields)}'}, status=status.HTTP_400_BAD_REQUEST)

            # Step 1: Fetch ProductUnit & Verify Activation Code
            try:
                product_unit = ProductUnit.objects.get(serial_number=serial_number)
            except ProductUnit.DoesNotExist:
                logger.error(f"ProductUnit with serial number {serial_number} does not exist.")
                return Response({'error': 'No product unit found with this serial number.'}, status=status.HTTP_404_NOT_FOUND)

            if not product_unit.activation_code:
                logger.error(f"ProductUnit {serial_number} has no activation code assigned.")
                return Response({'error': 'No activation code assigned to this product.'}, status=status.HTTP_400_BAD_REQUEST)

            if product_unit.activation_code.upper() != activation_code.upper():
                logger.warning(f"Activation code mismatch for {serial_number}. Expected: {product_unit.activation_code}, Received: {activation_code}")
                return Response({'error': 'Invalid activation code for this serial number.'}, status=status.HTTP_400_BAD_REQUEST)

            # Step 2: Fetch Warranty (or Create One)
            warranty, created = Warranty.objects.get_or_create(
                product_unit=product_unit,
                defaults={
                    'status': 'not_registered',
                    'purchase_date': now().date(),
                    'warranty_expiration_date': now().date() + timedelta(days=30 * 3)
                }
            )

            if warranty.status == 'active':
                logger.info(f"Warranty for {serial_number} is already active.")
                # Instead of returning an error, we return the warranty information.
                serializer = self.get_serializer(warranty)
                return Response({'active': True, 'warranty': serializer.data}, status=status.HTTP_200_OK)

            # Step 3: Find or Create Customer
            customer = self.get_or_create_customer(name, email, phone_number)

            # Step 4: Activate the Warranty
            self.activate_warranty(warranty, customer)

            return Response({'message': 'Warranty activated successfully.', 'customer_id': customer.id}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error during warranty activation: {e}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='validate/(?P<serial_number>[^/.]+)/(?P<activation_code>[^/.]+)')
    def validate_warranty(self, request, serial_number, activation_code):
        """
        Validate a warranty activation by checking the provided serial number and activation code.
        Returns product details if valid.
        If a warranty is already active, returns warranty info and active:true.
        """
        try:
            # Fetch the product unit
            product_unit = ProductUnit.objects.get(serial_number=serial_number)
        except ProductUnit.DoesNotExist:
            logger.error(f"ProductUnit with serial number {serial_number} does not exist.")
            return Response({'valid': False, 'error': 'No product unit found with this serial number.'}, status=status.HTTP_404_NOT_FOUND)

        if not product_unit.activation_code:
            logger.error(f"ProductUnit {serial_number} has no activation code assigned.")
            return Response({'valid': False, 'error': 'No activation code assigned to this product.'}, status=status.HTTP_400_BAD_REQUEST)

        if product_unit.activation_code.upper() != activation_code.upper():
            logger.warning(f"Activation code mismatch for {serial_number}. Expected: {product_unit.activation_code}, Received: {activation_code}")
            return Response({'valid': False, 'error': 'Invalid activation code for this serial number.'}, status=status.HTTP_400_BAD_REQUEST)
        

        # Check if a warranty already exists for this product unit.
        try:
            warranty = Warranty.objects.get(product_unit=product_unit)
            if warranty.status == 'active':
                # If already active, return the warranty info.
                serializer = self.get_serializer(warranty)
                return Response({'valid': True, 'active': True, 'warranty': serializer.data}, status=status.HTTP_200_OK)
        except Warranty.DoesNotExist:
            # No warranty exists, so the unit is available for activation.
            pass

        # Return product details if not active
        product_data = {
            'product_name': product_unit.product.name,
            'product_serial_number': product_unit.serial_number,
            # Add more product details as needed.
        }
        return Response({'valid': True, 'active': False, 'product': product_data}, status=status.HTTP_200_OK)

    def get_or_create_customer(self, name, email, phone_number):
        """
        Retrieve an existing customer by phone or email, or create a new one.
        """
        customer = Customer.objects.filter(models.Q(phone_number=phone_number) | models.Q(email=email)).first()
        if not customer:
            customer = Customer.objects.create(
                name=name,
                email=email,
                phone_number=phone_number,
                source_platform="manual"
            )
        return customer

    def activate_warranty(self, warranty, customer):
        """
        Activate the warranty and link it to the provided customer.
        """
        if warranty.status == 'active':
            raise ValueError("Warranty is already active.")

        warranty.customer = customer
        warranty.status = 'active'
        warranty.registered_at = now()
        warranty.save()

    @transaction.atomic
    @action(detail=True, methods=['post'])
    def extend(self, request, pk=None):
        """
        Extend a warranty for a specific product unit.
        """
        warranty = self.get_object()
        try:
            extension_period = request.data.get('extension_period', 1)  # Default to 1 month if not provided
            warranty.extend_warranty(extension_period)
            return Response({'status': 'Warranty extended successfully.'})
        except Exception as e:
            logger.error(f"Error extending warranty: {e}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='check/(?P<serial_number>[^/.]+)')
    def check_warranty(self, request, serial_number):
        """
        Check warranty status using the ProductUnit serial number.
        """
        try:
            warranty = Warranty.objects.select_related('product_unit').get(product_unit__serial_number=serial_number)
            serializer = self.get_serializer(warranty)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Warranty.DoesNotExist:
            return Response({'error': 'No warranty found for the provided serial number.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error when checking warranty: {e}", exc_info=True)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Registering WarrantyViewSet with the router
router = routers.DefaultRouter()
router.register(r'warranties', WarrantyViewSet, basename='warranty')

# URL Patterns
urlpatterns = [
    path('api/', include(router.urls)),
]
