from rest_framework import viewsets, filters, status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderItemSerializer, OrderDetailSerializer, OrderListSerializer

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
                'items__product__units'  # This matches the model relationship
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
    def ship(self, request, pk=None):
        """
        Ship an order.
        """
        order = self.get_object()
        order.transition_state('shipped')
        return Response({'status': 'Order shipped'})

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
    def mark_as_shipped(self, request, pk=None):
        """
        Mark an order item as shipped.
        """
        order_item = self.get_object()
        order_item.status = 'shipped'
        order_item.save()
        return Response({'status': 'Order item marked as shipped'})

    @action(detail=True, methods=['post'])
    def mark_as_returned(self, request, pk=None):
        """
        Mark an order item as returned.
        """
        order_item = self.get_object()
        order_item.status = 'returned'
        order_item.save()
        return Response({'status': 'Order item marked as returned'})

# Registering ViewSets with the router
