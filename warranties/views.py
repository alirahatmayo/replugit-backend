# warranty/views.py
from rest_framework import viewsets, filters, status, routers
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.urls import path, include
from django.db import transaction, models
from django.core.exceptions import ValidationError  # Added ValidationError import
import logging
from datetime import timedelta
from django.utils.timezone import now

from .models import Warranty
from products.models import ProductUnit
from customers.models import Customer
from customers.services import CustomerService
from .utils import validate_warranty_activation

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
        Anyone with valid credentials can activate the warranty.
        """
        try:
            data = request.data
            activation_code = data.get("activation_code")
            name = data.get("name")
            email = data.get("email")
            phone_number = data.get("phone_number")
            notes = data.get("notes", "")  # Optional notes field

            # Basic validation
            if not activation_code or not name or not (email or phone_number):
                return Response({
                    'error': 'Missing required fields: activation code, name, and either email or phone'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Step 1: Validate activation credentials
            is_valid, product_unit, error_message = validate_warranty_activation(serial_number, activation_code)
            
            if not is_valid:
                return Response({'error': error_message}, 
                               status=status.HTTP_400_BAD_REQUEST if product_unit else status.HTTP_404_NOT_FOUND)
                               
            # Step 2: Get warranty
            try:
                warranty = Warranty.objects.get(product_unit=product_unit)
            except Warranty.DoesNotExist:
                return Response({'error': 'No warranty found for this product.'}, status=status.HTTP_404_NOT_FOUND)

            # Step 3: Check if warranty is already active
            if warranty.status == 'active':
                serializer = self.get_serializer(warranty)
                return Response({'active': True, 'warranty': serializer.data}, status=status.HTTP_200_OK)

            # Step 4: Find or Create Customer
            customer = CustomerService.get_or_create_customer(name, email, phone_number)
            
            # Step 5: Check if activating customer is original purchaser (for logging purposes only)
            is_original_purchaser = False
            if warranty.order and warranty.order.customer:
                original_customer = warranty.order.customer
                if (email and original_customer.email and email.lower() == original_customer.email.lower()) or \
                   (phone_number and original_customer.phone_number and phone_number == original_customer.phone_number):
                    is_original_purchaser = True
                    
            # Add note about relationship if not original purchaser
            activation_notes = notes
            if not is_original_purchaser and warranty.order and warranty.order.customer:
                if not activation_notes:
                    activation_notes = "Activated by someone other than original purchaser"

            # Step 6: Activate the Warranty
            try:
                warranty.activate(customer, notes=activation_notes)
                serializer = self.get_serializer(warranty)
                return Response({
                    'message': 'Warranty activated successfully.',
                    'warranty': serializer.data
                }, status=status.HTTP_200_OK)
                
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
        # Use utility function for validation
        is_valid, product_unit, error_message = validate_warranty_activation(serial_number, activation_code)
        
        if not is_valid:
            return Response({
                'valid': False,
                'error': error_message
            }, status=status.HTTP_400_BAD_REQUEST if product_unit else status.HTTP_404_NOT_FOUND)
        
        # Everything checks out, return success and product details
        try:
            warranty = Warranty.objects.get(product_unit=product_unit)
            serializer = self.get_serializer(warranty)
            return Response({
                'valid': True,
                'warranty': serializer.data,
                'product': {
                    'name': product_unit.product.name if hasattr(product_unit, 'product') else None,
                    'sku': product_unit.product.sku if hasattr(product_unit, 'product') else None,
                }
            })
        except Warranty.DoesNotExist:
            # No warranty found, but credentials are valid
            return Response({
                'valid': True,
                'product': {
                    'name': product_unit.product.name if hasattr(product_unit, 'product') else None,
                    'sku': product_unit.product.sku if hasattr(product_unit, 'product') else None,
                }
            })


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

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reset(self, request, pk=None):
        """
        Generic endpoint to reset a warranty to not_registered status.
        """
        warranty = self.get_object()
        
        try:
            reason = request.data.get('reason', '')
            keep_customer = request.data.get('keep_customer', False)
            
            warranty.reset_warranty(
                user=request.user, 
                reason=reason,
                keep_customer=keep_customer
            )
            
            return Response({
                'status': 'success',
                'message': 'Warranty has been reset.',
                'warranty_id': warranty.id,
                'product_unit': warranty.product_unit.serial_number
            })
        except ValidationError as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

# Registering WarrantyViewSet with the router
router = routers.DefaultRouter()
router.register(r'warranties', WarrantyViewSet, basename='warranty')

