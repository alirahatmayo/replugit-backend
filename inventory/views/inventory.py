import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404

from ..models import Inventory, InventoryAdjustment, InventoryHistory, InventoryReceipt
from ..serializers import (
    InventorySerializer, InventoryDetailSerializer, 
    InventoryHistorySerializer, InventoryUpdateSerializer,
    InventoryAdjustmentSerializer, InventoryReceiptSerializer
)
from ..utils import success_response, error_response
from ..services.inventory_service import InventoryService
from products.models import Product, ProductUnit
from products.serializers import ProductUnitSerializer

logger = logging.getLogger(__name__)

class InventoryViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing inventory records.
    """
    queryset = Inventory.objects.all().select_related('product', 'location')
    serializer_class = InventorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'status': ['exact', 'in'],
        'platform': ['exact', 'in'],
        'location': ['exact', 'in'],
        'quantity': ['exact', 'lt', 'lte', 'gt', 'gte'],
    }
    search_fields = ['product__sku', 'product__name', 'platform_sku']
    ordering_fields = ['quantity', 'updated_at', 'product__sku']
    
    def get_serializer_class(self):
        """Return different serializers for list vs detail views"""
        if self.action == 'retrieve':
            return InventoryDetailSerializer
        return InventorySerializer
    
    @action(detail=False, methods=['post'])
    def update_inventory(self, request):
        """
        Update inventory quantity with audit trail.
        """
        serializer = InventoryUpdateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response("Invalid data", errors=serializer.errors)
        
        sku = serializer.validated_data['sku']
        platform = serializer.validated_data['platform']
        new_quantity = serializer.validated_data['quantity']
        location_code = serializer.validated_data.get('location', 'DEFAULT')
        reason = serializer.validated_data.get('reason', 'MANUAL')
        reference = serializer.validated_data.get('reference', '')
        notes = serializer.validated_data.get('notes', '')
        
        try:
            # Find product by SKU
            product = get_object_or_404(Product, sku=sku)
            
            # Get or create location
            from ..models import Location
            location, _ = Location.objects.get_or_create(
                code=location_code,
                defaults={'name': location_code.title()}
            )
            
            # Use inventory service to update
            inventory, history = InventoryService.update_inventory(
                product=product,
                platform=platform,
                location=location,
                new_quantity=new_quantity,
                reason=reason,
                reference=reference,
                notes=notes,
                user=request.user if request.user.is_authenticated else None
            )
            
            return success_response({
                'inventory': InventorySerializer(inventory).data,
                'history': InventoryHistorySerializer(history).data
            }, message="Inventory updated successfully")
                
        except Product.DoesNotExist:
            return error_response(
                f'Product with SKU {sku} not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating inventory: {str(e)}", exc_info=True)
            return error_response(
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get all low stock items"""
        threshold = request.query_params.get('threshold')
        queryset = InventoryService.get_low_stock_items(threshold)
        serializer = self.get_serializer(queryset, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['get'], url_path='detailed')
    def detailed_inventory(self, request, pk=None):
        """Get comprehensive inventory data for a specific product"""
        inventory = self.get_object()
        product = inventory.product
        
        # Get inventory history
        history = InventoryHistory.objects.filter(
            inventory=inventory
        ).order_by('-timestamp')[:20]
        
        # Get available units
        available_units = ProductUnit.objects.filter(
            product=product,
            status='in_stock',
            location=inventory.location
        ).count()
        
        # Get units by status
        units_by_status = {
            status[0]: ProductUnit.objects.filter(
                product=product, 
                status=status[0],
                location=inventory.location
            ).count()
            for status in ProductUnit.STATUS_CHOICES
        }
        
        # Get pending adjustments
        pending_adjustments = InventoryAdjustment.objects.filter(
            inventory=inventory,
            status='PENDING'
        ).order_by('-created_at')
        
        # Get recent receipts
        recent_receipts = InventoryReceipt.objects.filter(
            product=product,
            location=inventory.location
        ).order_by('-receipt_date')[:5]
        
        # Build response
        response_data = {
            'inventory': InventoryDetailSerializer(inventory).data,
            'history': InventoryHistorySerializer(history, many=True).data,
            'units': {
                'available': available_units,
                'by_status': units_by_status,
            },
            'pending_adjustments': InventoryAdjustmentSerializer(pending_adjustments, many=True).data,
            'recent_receipts': InventoryReceiptSerializer(recent_receipts, many=True).data,
        }
        
        return success_response(response_data)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Update multiple inventory records at once"""
        items = request.data.get('items', [])
        
        if not items:
            return error_response("No items provided")
        
        results = {
            'success': [],
            'errors': []
        }
        
        from django.db import transaction
        with transaction.atomic():
            for item in items:
                try:
                    # Get required fields
                    inventory_id = item.get('id')
                    quantity = item.get('quantity')
                    
                    if not inventory_id or quantity is None:
                        results['errors'].append({
                            'item': item,
                            'error': "Missing required fields (id, quantity)"
                        })
                        continue
                    
                    # Get the inventory record
                    try:
                        inventory = Inventory.objects.get(pk=inventory_id)
                    except Inventory.DoesNotExist:
                        results['errors'].append({
                            'item': item,
                            'error': f"Inventory with ID {inventory_id} not found"
                        })
                        continue
                    
                    # Calculate adjustment
                    adjustment = quantity - inventory.quantity
                    
                    # Skip if no change
                    if adjustment == 0:
                        results['success'].append({
                            'id': inventory_id,
                            'message': "No change needed",
                            'inventory': InventorySerializer(inventory).data
                        })
                        continue
                    
                    # Apply adjustment
                    reason = item.get('reason', 'MANUAL')
                    reference = item.get('reference', '')
                    notes = item.get('notes', '')
                    
                    history = inventory.adjust_quantity(
                        adjustment=adjustment,
                        reason=reason,
                        reference=reference,
                        notes=notes,
                        user=request.user if request.user.is_authenticated else None
                    )
                    
                    results['success'].append({
                        'id': inventory_id,
                        'adjustment': adjustment,
                        'history_id': str(history.id),
                        'inventory': InventorySerializer(inventory).data
                    })
                    
                except Exception as e:
                    results['errors'].append({
                        'item': item,
                        'error': str(e)
                    })
        
        return success_response(results)