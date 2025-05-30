import logging
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..models import InventoryReceipt, Inventory
from ..serializers import InventoryReceiptSerializer
from ..utils import success_response, error_response
from ..services.receipt_service import ReceiptService
from products.models import ProductUnit
from products.serializers import ProductUnitListSerializer, ProductUnitSerializer

logger = logging.getLogger(__name__)

class InventoryReceiptViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing inventory receipts.
    """
    queryset = InventoryReceipt.objects.select_related('product', 'location').all()
    serializer_class = InventoryReceiptSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product', 'location', 'receipt_date', 'batch_code', 'requires_unit_qc']
    search_fields = ['product__name', 'product__sku', 'reference', 'batch_code']
    ordering_fields = ['receipt_date', 'quantity']
    ordering = ['-receipt_date']
    
    def perform_create(self, serializer):
        """Add current user as created_by"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def units(self, request, pk=None):
        """
        Get all product units created from this receipt.
        Uses the metadata field instead of a relationship model.
        """
        receipt = self.get_object()
        
        # Find units with metadata referencing this receipt
        units = ProductUnit.objects.filter(
            metadata__receipt_id=str(receipt.id)
        ).order_by('created_at')
        
        # Serialize units for response
        serializer = ProductUnitListSerializer(units, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['get'])
    def pending_qc_units(self, request, pk=None):
        """Get units from this receipt that need QC"""
        receipt = self.get_object()
        
        pending_units = ProductUnit.objects.filter(
            status='pending_qc',
            metadata__receipt_id=str(receipt.id)
        )
        
        serializer = ProductUnitSerializer(pending_units, many=True)
        return success_response(serializer.data)
        
    @action(detail=True, methods=['post'])
    def generate_units(self, request, pk=None):
        """Generate product units for this receipt"""
        receipt = self.get_object()
        from django.conf import settings
        
        # Check if method exists to avoid AttributeError
        if not hasattr(receipt, 'should_create_product_units'):
            return error_response("Receipt doesn't support unit creation")
            
        # Check if units should be created
        if not receipt.should_create_product_units():
            # Filter out None values for clean response
            reasons = [
                reason for reason in [
                    "Product not serialized" if hasattr(receipt.product, 'is_serialized') and not receipt.product.is_serialized else None,
                    "Receipt marked to not create units" if hasattr(receipt, 'create_product_units') and not receipt.create_product_units else None,
                    "System configuration disallows unit creation" if not getattr(settings, 'INVENTORY_TRACK_UNITS', True) else None,
                ] if reason is not None
            ]
            
            return error_response(
                "Unit creation not allowed for this receipt",
                errors={"reasons": reasons or ["Unknown reason"]}
            )
        
        try:
            with transaction.atomic():
                # Generate units
                units = receipt.generate_product_units()
                
                # Return response with serialized unit data
                return success_response({
                    "units_created": len(units),
                    "units": ProductUnitListSerializer(units, many=True).data
                }, message=f"Generated {len(units)} product units")
                
        except Exception as e:
            logger.error(f"Error generating units: {str(e)}", exc_info=True)
            transaction.set_rollback(True)
            return error_response(
                f"Error generating units: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, *args, **kwargs):
        """Enhanced creation endpoint for inventory receipts"""
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response("Invalid data", errors=serializer.errors)
        
        try:
            with transaction.atomic():
                # Use service to create receipt
                receipt, inventory, history, units = ReceiptService.create_receipt(
                    data=serializer.validated_data,
                    user=request.user
                )
                
                # Build response
                response_data = {
                    'receipt': self.get_serializer(receipt).data,
                    'inventory_update': {
                        'previous_quantity': history.previous_quantity,
                        'new_quantity': history.new_quantity,
                        'change': history.change
                    },
                    'units_created': len(units),
                    'units_require_qc': receipt.requires_unit_qc,
                    'status': "Receipt processed successfully"
                }
                
                # Return the response
                return success_response(
                    response_data, 
                    message="Inventory receipt processed successfully",
                    status_code=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            logger.error(f"Error creating receipt: {str(e)}", exc_info=True)
            return error_response(
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='process-qc')
    def process_qc(self, request, pk=None):
        """Process QC for units from this receipt"""
        receipt = self.get_object()
        qc_data = request.data.get('units', [])
        
        if not qc_data:
            return error_response("No QC data provided")
            
        try:
            with transaction.atomic():
                # Use service to process QC
                results, processed_units, qc_record = ReceiptService.process_qc(
                    receipt=receipt,
                    qc_data=qc_data,
                    user=request.user
                )
                
                # Build response
                return success_response({
                    'results': results,
                    'receipt_id': str(receipt.id),
                    'qc_record': str(qc_record.id) if qc_record else None,
                    'processed_units': ProductUnitSerializer(processed_units, many=True).data
                })
                
        except Exception as e:
            logger.error(f"Error processing QC: {str(e)}", exc_info=True)
            return error_response(
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )