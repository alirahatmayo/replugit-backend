from rest_framework import viewsets, filters, status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.http import HttpResponse
from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderItemSerializer, OrderDetailSerializer, OrderListSerializer
import logging

logger = logging.getLogger(__name__)

class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Orders with different detail levels.
    """
    queryset = Order.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['platform', 'state', 'order_date', 'customer']
    search_fields = ['order_number', 'customer__name', 'platform']
    ordering_fields = ['order_date', 'updated_at']
    ordering = ['-order_date']
    lookup_field = 'order_number'

    def get_serializer_class(self):
        """
        Return different serializers based on the action.
        """
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return OrderDetailSerializer
        return OrderListSerializer

    def get_queryset(self):
        """
        Optimize queryset based on the action.
        """
        queryset = Order.objects.select_related('customer')
        
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            # Full detail view needs all related data
            return queryset.prefetch_related(
                'items',
                'items__product',
                'items__assigned_units_relation',  # This is correct
                'items__product__inventory_records',  # Fixed related_name
                'items__product__inventory_records__location'  # Fixed related_name
            )
        
        # List view needs minimal related data
        return queryset.prefetch_related('items')

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """
        Confirm an order.
        """
        order = self.get_object()
        order.transition_state('confirmed')
        return Response({'status': 'Order confirmed'})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def ship(self, request, pk=None):
        """
        Ship an order and mark all assigned product units as sold.
        This triggers warranty creation for serialized products.
        """
        order = self.get_object()
        
        # First, transition the order state
        order.transition_state('shipped')
        
        # Now mark all assigned product units as sold
        units_updated = 0
        for item in order.items.all():
            for product_unit in item.assigned_units_relation.all():
                try:
                    # Use the mark_as_sold method which will create warranties via signal
                    product_unit.mark_as_sold(order_item=item)
                    units_updated += 1
                except Exception as e:
                    logger.error(f"Error marking unit {product_unit.id} as sold: {str(e)}")
        
        return Response({
            'status': 'Order shipped',
            'units_marked_as_sold': units_updated
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel an order.
        """
        order = self.get_object()
        order.transition_state('cancelled')
        return Response({'status': 'Order cancelled'})

class OrderItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing OrderItems.
    Supports filtering, searching, and nested product information.
    """
    queryset = OrderItem.objects.select_related('order', 'product').all()
    serializer_class = OrderItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'order', 'product', 'created_at']
    search_fields = ['order__order_number', 'product__name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def mark_as_shipped(self, request, pk=None):
        """
        Mark an order item as shipped and mark all its product units as sold.
        This triggers warranty creation for serialized products.
        """
        order_item = self.get_object()
        order_item.status = 'shipped'
        order_item.save()
        
        # Mark all assigned product units as sold
        units_updated = 0
        for product_unit in order_item.assigned_units_relation.all():
            try:
                # Use the mark_as_sold method which will create warranties via signal
                product_unit.mark_as_sold(order_item=order_item)
                units_updated += 1
            except Exception as e:
                logger.error(f"Error marking unit {product_unit.id} as sold: {str(e)}")
        
        return Response({
            'status': 'Order item marked as shipped',
            'units_marked_as_sold': units_updated
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def mark_as_returned(self, request, pk=None):
        """
        Mark an order item as returned and update product unit statuses.
        """
        order_item = self.get_object()
        order_item.status = 'returned'
        order_item.save()
        
        # Update all assigned product units to returned status
        units_updated = 0
        for product_unit in order_item.assigned_units_relation.all():
            try:
                # Set status back to returned
                product_unit.status = 'returned'
                product_unit.save()
                
                # Optionally: Reset any warranties
                from warranties.models import Warranty
                try:
                    warranty = Warranty.objects.get(product_unit=product_unit)
                    warranty.reset_warranty(reason="Product returned")
                except Warranty.DoesNotExist:
                    pass  # No warranty to reset
                    
                units_updated += 1
            except Exception as e:
                logger.error(f"Error updating returned unit {product_unit.id}: {str(e)}")
        
        return Response({
            'status': 'Order item marked as returned',
            'units_updated': units_updated
        })
