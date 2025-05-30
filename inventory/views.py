# Standard library imports
import logging

# Django imports
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDay, TruncMonth

# Third-party imports
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import api_view, action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

# Local imports
from .models import (
    Inventory, Location, InventoryHistory, 
    StockAlert, InventoryAdjustment, InventoryReceipt
)
from .serializers import (
    InventorySerializer, InventoryDetailSerializer, LocationSerializer, 
    InventoryHistorySerializer, StockAlertSerializer, InventoryAdjustmentSerializer,
    InventoryUpdateSerializer, InventoryReceiptSerializer
)
from products.models import Product, ProductUnit
from products.serializers import ProductUnitSerializer, ProductUnitListSerializer
# from .services import inventory_service

# Create logger for this module
logger = logging.getLogger(__name__)

# Helper methods for consistent API responses
def success_response(data=None, message=None, status_code=status.HTTP_200_OK):
    """Generate consistent success response format"""
    response = {'success': True}
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    return Response(response, status=status_code)

def error_response(message, status_code=status.HTTP_400_BAD_REQUEST, errors=None):
    """Generate consistent error response format"""
    response = {'success': False, 'error': message}
    if errors:
        response['errors'] = errors
    return Response(response, status=status_code)


class LocationViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing inventory locations/warehouses.
    """
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'code']


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
            with transaction.atomic():
                # Find product by SKU
                product = get_object_or_404(Product, sku=sku)
                
                # Get or create location
                location, _ = Location.objects.get_or_create(
                    code=location_code,
                    defaults={'name': location_code.title()}
                )
                
                # Get or create inventory record
                inventory, created = Inventory.objects.get_or_create(
                    product=product,
                    platform=platform,
                    location=location,
                    defaults={'quantity': 0}
                )
                
                # Adjust quantity (uses model's adjust_quantity method)
                adjustment = new_quantity - inventory.quantity
                history = inventory.adjust_quantity(
                    adjustment=adjustment,
                    reason=reason,
                    reference=reference,
                    notes=notes,
                    user=request.user if request.user.is_authenticated else None
                )
                
                # Update last sync time if this is from a platform sync
                if reason == 'SYNC':
                    inventory.last_sync = timezone.now()
                    inventory.save(update_fields=['last_sync'])
                
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
    
    # Uncomment when inventory service is ready
    # @action(detail=False, methods=['post'])
    # def sync(self, request):
    #     """Synchronize inventory with platform"""
    #     sku = request.data.get('sku')
    #     platform = request.data.get('platform', 'walmart')
    #     
    #     if not sku:
    #         return error_response('SKU is required')
    #         
    #     try:
    #         result = inventory_service.sync_platform_inventory(
    #             sku=sku,
    #             platform=platform
    #         )
    #         return success_response(result)
    #     except Product.DoesNotExist:
    #         return error_response(
    #             f'Product with SKU {sku} not found',
    #             status_code=status.HTTP_404_NOT_FOUND
    #         )
    #     except Exception as e:
    #         logger.error(f"Error syncing inventory: {str(e)}", exc_info=True)
    #         return error_response(
    #             str(e),
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get all low stock items"""
        threshold = request.query_params.get('threshold')
        
        queryset = self.queryset.filter(status='LOW_STOCK')
        if threshold:
            try:
                threshold = int(threshold)
                queryset = queryset.filter(quantity__lte=threshold)
            except ValueError:
                pass
                
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


class InventoryHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for viewing inventory history records.
    Read-only to preserve audit integrity.
    """
    queryset = InventoryHistory.objects.all().select_related(
        'inventory', 'inventory__product', 'inventory__location', 'adjusted_by'
    )
    serializer_class = InventoryHistorySerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['reason', 'inventory__product', 'inventory__location']
    ordering_fields = ['timestamp', 'change']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """Add additional filtering by query parameters"""
        queryset = super().get_queryset()
        product_sku = self.request.query_params.get('product_sku')
        platform = self.request.query_params.get('platform')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if product_sku:
            queryset = queryset.filter(inventory__product__sku=product_sku)
            
        if platform:
            queryset = queryset.filter(inventory__platform=platform)
            
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
            
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
            
        return queryset


class InventoryReceiptViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing inventory receipts.
    """
    queryset = InventoryReceipt.objects.select_related('product', 'location').all()
    serializer_class = InventoryReceiptSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
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
        
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def generate_units(self, request, pk=None):
        """Generate product units for this receipt"""
        receipt = self.get_object()
        
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
        
        with transaction.atomic():
            # Create receipt and save
            receipt = serializer.save(created_by=request.user)
            
            # Generate units if needed (moved from model.save to here for better control)
            units = []
            if receipt.should_create_product_units():
                units = receipt.generate_product_units()
            
            # Update inventory
            inventory, created = Inventory.objects.get_or_create(
                product=receipt.product,
                location=receipt.location,
                defaults={'quantity': 0}
            )
            
            history = inventory.adjust_quantity(
                adjustment=receipt.quantity,
                reason="PURCHASE",
                reference=f"Receipt #{receipt.id}",
                notes=f"Inventory receipt from {receipt.get_seller_name() or 'unknown seller'}",
                user=request.user
            )
            
            # Build response
            response_data = {
                'receipt': serializer.data,
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

    @action(detail=True, methods=['post'], url_path='process-qc')
    def process_qc(self, request, pk=None):
        """Process QC for units from this receipt"""
        receipt = self.get_object()
        qc_data = request.data.get('units', [])
        results = {'passed': 0, 'failed': 0, 'errors': []}
        
        with transaction.atomic():
            for unit_data in qc_data:
                try:
                    unit_id = unit_data.get('id')
                    qc_result = unit_data.get('result')  # 'pass' or 'fail'
                    notes = unit_data.get('notes', '')
                    
                    if not unit_id or not qc_result:
                        results['errors'].append({
                            'unit': unit_id,
                            'error': 'Missing unit_id or result'
                        })
                        continue
                    
                    # Get the unit
                    try:
                        unit = ProductUnit.objects.get(
                            id=unit_id,
                            status='pending_qc',
                            metadata__receipt_id=str(receipt.id)
                        )
                    except ProductUnit.DoesNotExist:
                        results['errors'].append({
                            'unit': unit_id,
                            'error': 'Unit not found or not pending QC'
                        })
                        continue
                    
                    # Update unit status
                    if qc_result.lower() == 'pass':
                        unit.status = 'in_stock'
                        results['passed'] += 1
                    else:
                        unit.status = 'defective'
                        results['failed'] += 1
                    
                    # Update unit metadata
                    unit.metadata = unit.metadata or {}
                    if 'qc' not in unit.metadata:
                        unit.metadata['qc'] = {}
                        
                    unit.metadata['qc']['result'] = qc_result.upper()
                    unit.metadata['qc']['notes'] = notes
                    unit.metadata['qc']['processed_at'] = timezone.now().isoformat()
                    unit.metadata['qc']['processed_by'] = request.user.username
                    
                    unit.save()
                    
                except Exception as e:
                    results['errors'].append({
                        'unit': unit_data.get('id'),
                        'error': str(e)
                    })
            
            # Update main QC record if it exists
            qc_record = receipt.quality_control
            if qc_record:
                qc_record.status = 'COMPLETED'
                qc_record.inspected_by = request.user
                qc_record.inspected_at = timezone.now()
                qc_record.save()
        
        return success_response({
            'results': results,
            'receipt_id': str(receipt.id),
            'qc_record': str(qc_record.id) if qc_record else None
        })


class InventoryAdjustmentViewSet(viewsets.ModelViewSet):
    """
    API endpoints for inventory adjustments with approval workflow.
    """
    queryset = InventoryAdjustment.objects.all().select_related(
        'inventory', 'inventory__product', 'inventory__location', 
        'created_by', 'approved_by'
    )
    serializer_class = InventoryAdjustmentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'reason', 'inventory__product', 'inventory__location']
    search_fields = ['reference', 'notes', 'inventory__product__sku', 'inventory__product__name']
    ordering_fields = ['created_at', 'approved_at', 'quantity_change']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        """Add current user as created_by"""
        serializer.save(created_by=self.request.user)
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """API endpoint to approve an adjustment"""
        adjustment = self.get_object()
        
        if adjustment.status != 'PENDING':
            return error_response(f'Cannot approve adjustment with status {adjustment.status}')
            
        try:
            from .services import InventoryService
            success = InventoryService.process_adjustment(adjustment, request.user)
            
            if success:
                return success_response(
                    InventoryAdjustmentSerializer(adjustment).data,
                    message="Adjustment approved"
                )
            else:
                return error_response("Could not approve adjustment")
                
        except Exception as e:
            logger.error(f"Error approving adjustment: {str(e)}", exc_info=True)
            return error_response(
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """API endpoint to reject an adjustment"""
        adjustment = self.get_object()
        rejection_reason = request.data.get('reason', '')
        
        if adjustment.status != 'PENDING':
            return error_response(f'Cannot reject adjustment with status {adjustment.status}')
            
        try:
            # Add rejection reason to notes if provided
            if rejection_reason and not adjustment.notes:
                adjustment.notes = f"Rejected: {rejection_reason}"
            elif rejection_reason:
                adjustment.notes += f"\n\nRejected: {rejection_reason}"
                
            success = adjustment.reject(request.user)
            
            if success:
                return success_response(
                    InventoryAdjustmentSerializer(adjustment).data,
                    message="Adjustment rejected"
                )
            else:
                return error_response("Could not reject adjustment")
                
        except Exception as e:
            logger.error(f"Error rejecting adjustment: {str(e)}", exc_info=True)
            return error_response(
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Units data is now accessible through InventoryReceiptViewSet.units action
# Keeping this endpoint for backward compatibility
@api_view(['GET'])
def test_receipt_units(request, receipt_id):
    """
    Legacy endpoint to check if units were created for a receipt.
    Use /api/inventory/receipts/{id}/units/ for new integrations.
    """
    try:
        receipt = InventoryReceipt.objects.get(id=receipt_id)
        units = ProductUnit.objects.filter(metadata__receipt_id=str(receipt_id))
        
        return success_response({
            'receipt': {
                'id': str(receipt.id),
                'product': receipt.product.name,
                'quantity': receipt.quantity,
                'reference': receipt.reference
            },
            'units_created': units.count(),
            'units': [
                {
                    'id': str(unit.id),
                    'serial': unit.serial_number,
                    'status': unit.status
                }
                for unit in units
            ]
        })
    except InventoryReceipt.DoesNotExist:
        return error_response('Receipt not found', status_code=status.HTTP_404_NOT_FOUND)

# Add this endpoint to your views
@api_view(['GET'])
def inventory_dashboard(request):
    """
    Get comprehensive inventory dashboard data for frontend
    """
    # Get total inventory value and counts
    inventory_summary = Inventory.objects.aggregate(
        total_items=Count('id'),
        total_quantity=Sum('quantity'),
        low_stock_count=Count('id', filter=Q(status='LOW_STOCK')),
        out_of_stock_count=Count('id', filter=Q(status='OUT_OF_STOCK')),
        total_value=Sum(
            ExpressionWrapper(
                F('quantity') * F('product__cost_price'), 
                output_field=DecimalField()
            )
        )
    )
    
    # Get top products by quantity
    top_products = Inventory.objects.select_related('product').order_by('-quantity')[:10]
    top_products_data = [
        {
            'product_name': item.product.name,
            'product_sku': item.product.sku,
            'quantity': item.quantity,
            'status': item.status,
            'location': item.location.name,
            'product_id': str(item.product.id)
        }
        for item in top_products
    ]
    
    # Get recent activity
    recent_history = InventoryHistory.objects.select_related(
        'inventory__product', 'adjusted_by'
    ).order_by('-timestamp')[:20]
    
    recent_activity = [
        {
            'id': str(item.id),
            'product_name': item.inventory.product.name,
            'product_sku': item.inventory.product.sku,
            'change': item.change,
            'timestamp': item.timestamp,
            'reason': item.reason,
            'user': item.adjusted_by.username if item.adjusted_by else None,
            'reference': item.reference
        }
        for item in recent_history
    ]
    
    # Get recent receipts
    recent_receipts = InventoryReceipt.objects.select_related(
        'product', 'location', 'created_by'
    ).order_by('-receipt_date')[:10]
    
    receipts_data = [
        {
            'id': str(receipt.id),
            'product_name': receipt.product.name,
            'quantity': receipt.quantity,
            'location': receipt.location.name,
            'date': receipt.receipt_date,
            'reference': receipt.reference,
            'created_by': receipt.created_by.username if receipt.created_by else None,
            'units_created': ProductUnit.objects.filter(metadata__receipt_id=str(receipt.id)).count()
        }
        for receipt in recent_receipts
    ]
    
    # Return comprehensive dashboard data
    return success_response({
        'summary': inventory_summary,
        'top_products': top_products_data,
        'recent_activity': recent_activity,
        'recent_receipts': receipts_data,
        'status_counts': {
            'IN_STOCK': Inventory.objects.filter(status='IN_STOCK').count(),
            'LOW_STOCK': Inventory.objects.filter(status='LOW_STOCK').count(),
            'OUT_OF_STOCK': Inventory.objects.filter(status='OUT_OF_STOCK').count(),
            'DISCONTINUED': Inventory.objects.filter(status='DISCONTINUED').count()
        }
    })

@api_view(['POST'])
def allocate_units(request):
    """Allocate inventory units to an order"""
    order_id = request.data.get('order_id')
    items = request.data.get('items', [])
    
    if not order_id:
        return error_response("Missing order_id")
        
    if not items:
        return error_response("No items to allocate")
    
    results = {'success': [], 'errors': []}
    
    with transaction.atomic():
        for item in items:
            try:
                item_id = item.get('order_item_id')
                product_id = item.get('product_id')
                quantity = item.get('quantity', 1)
                
                # Get the order item
                from orders.models import OrderItem
                try:
                    order_item = OrderItem.objects.get(id=item_id)
                except OrderItem.DoesNotExist:
                    results['errors'].append({
                        'item_id': item_id,
                        'error': "Order item not found"
                    })
                    continue
                
                # Find available units of this product
                available_units = ProductUnit.objects.filter(
                    product_id=product_id,
                    status='in_stock'
                ).order_by('created_at')[:quantity]
                
                # Check if we have enough units
                if available_units.count() < quantity:
                    results['errors'].append({
                        'item_id': item_id,
                        'error': f"Not enough units available. Requested: {quantity}, Available: {available_units.count()}"
                    })
                    continue
                
                # Allocate each unit to the order item
                allocated_units = []
                for unit in available_units:
                    try:
                        unit.assign_to_order_item(
                            order_item=order_item,
                            user=request.user,
                            notes=f"Allocated to order {order_id}"
                        )
                        allocated_units.append(str(unit.id))
                    except Exception as e:
                        results['errors'].append({
                            'unit_id': str(unit.id),
                            'error': str(e)
                        })
                
                results['success'].append({
                    'item_id': item_id,
                    'product_id': product_id,
                    'allocated_count': len(allocated_units),
                    'allocated_units': allocated_units
                })
                
                # Update inventory reserved quantity
                inventory = Inventory.objects.filter(product_id=product_id).first()
                if inventory:
                    inventory.reserved_quantity += len(allocated_units)
                    inventory.save()
                
            except Exception as e:
                results['errors'].append({
                    'item': item,
                    'error': str(e)
                })
    
    return success_response(results)

